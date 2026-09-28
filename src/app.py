"""FastAPI service and single-page UI.

    uvicorn src.app:app --port 8000
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import baseline, learn, llm, memory
from .config import DATA, HOLDBACK, ROOT
from .ingest import IngestError, load_file, parse_markdown
from .reasoning import Pipeline
from .schema import (AcceptRequest, AskRequest, AskResponse, DecisionRecord, IngestRequest, SignalRequest,
                     SignalResponse, StatelessResponse)
from .store import Store

WEB = ROOT / "web" / "dist"  # React build (cd web && npm run build)
@asynccontextmanager
async def _lifespan(_: FastAPI):
    yield
    await memory.aclose()  # close Hindsight's HTTP session on shutdown


app = FastAPI(title="WHY — state-aware decision memory", lifespan=_lifespan)
store = Store()
pipeline = Pipeline(store)


@app.exception_handler(memory.MemoryError_)
async def _memory_down(_: Request, e: Exception):
    return JSONResponse(status_code=503, content={"detail": f"Hindsight memory unavailable: {e}"})


@app.exception_handler(llm.LLMError)
async def _llm_down(_: Request, e: Exception):
    return JSONResponse(status_code=502, content={"detail": f"LLM error: {e}"})


@app.exception_handler(IngestError)
async def _bad_doc(_: Request, e: Exception):
    return JSONResponse(status_code=422, content={"detail": str(e)})


@app.get("/health")
async def health():
    return {"hindsight": await memory.ping(), "records": len(store.all())}


@app.post("/api/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    return await pipeline.ask(req.question, req.current_context)


@app.post("/api/ask/stream")
async def ask_stream(req: AskRequest):
    """Same pipeline as /api/ask, streamed as Server-Sent Events: one event per stage, then the result."""
    queue: asyncio.Queue = asyncio.Queue()

    async def run():
        try:
            r = await pipeline.ask(req.question, req.current_context, emit=queue.put)
            await queue.put({"stage": "result", "data": r.model_dump(mode="json")})
        except memory.MemoryError_ as e:
            await queue.put({"stage": "error", "detail": f"Hindsight memory unavailable: {e}"})
        except Exception as e:
            await queue.put({"stage": "error", "detail": f"{type(e).__name__}: {e}"})
        finally:
            await queue.put(None)

    task = asyncio.create_task(run())

    async def events():
        try:
            while (item := await queue.get()) is not None:
                yield f"data: {json.dumps(item, default=str)}\n\n"
        finally:
            task.cancel()

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/ask/stateless", response_model=StatelessResponse)
async def ask_stateless(req: AskRequest):
    r = await baseline.no_memory(req.question, req.current_context)
    return StatelessResponse(answer=r.answer, verdict=r.verdict, timings_ms=r.timings_ms)


@app.post("/api/signals", response_model=SignalResponse)
async def signals(req: SignalRequest):
    return await learn.record_signal(store, req.title, req.detail)


@app.post("/api/ingest")
async def ingest(req: IngestRequest):
    meta, _ = parse_markdown(req.markdown)
    rec, warnings = await learn.ingest_markdown(store, req.markdown, f"WHY UI ({meta.get('id', 'upload')})")
    return {"record": rec.model_dump(mode="json"), "warnings": warnings}


@app.get("/api/holdback")
async def holdback():
    out = []
    for p in sorted(HOLDBACK.glob("*.md")):
        meta, _ = parse_markdown(p.read_text(encoding="utf-8"))
        out.append({"id": meta["id"], "title": meta["title"], "date": meta["date"],
                    "ingested": store.get(meta["id"]) is not None})
    return out


@app.post("/api/holdback/{rid}")
async def ingest_holdback(rid: str):
    path = HOLDBACK / f"{rid}.md"
    if not path.exists():
        raise HTTPException(404, f"no held-back document {rid}")
    text, ref = load_file(path)
    rec, warnings = await learn.ingest_markdown(store, text, ref)
    return {"record": rec.model_dump(mode="json"), "warnings": warnings}


@app.post("/api/decisions/accept")
async def accept(req: AcceptRequest):
    if req.based_on and not isinstance(store.get(req.based_on), DecisionRecord):
        raise HTTPException(404, f"unknown decision {req.based_on}")
    rec = await learn.accept_decision(store, req)
    return rec.model_dump(mode="json")


@app.get("/api/timeline")
async def timeline():
    return [{"id": r.id, "kind": r.kind, "date": r.date.isoformat(), "title": r.title,
             "status": getattr(r, "status", None)} for r in store.all()]


@app.get("/api/records/{rid}")
async def record(rid: str):
    r = store.get(rid)
    if r is None:
        raise HTTPException(404, f"unknown record {rid}")
    return r.model_dump(mode="json")


def _json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@app.get("/api/casestudy")
async def casestudy():
    """Case-study page: organization profile, its decision history, and WHY's decision health board."""
    recs = store.all()
    return {
        "profile": _json(DATA / "casestudy" / "keelwright.json"),
        "health": _json(DATA / "casestudy" / "health.json"),
        "records": [{"id": r.id, "kind": r.kind, "date": r.date.isoformat(), "title": r.title,
                     "who": getattr(r, "team", "") or ", ".join(getattr(r, "authors", []) or []) or getattr(r, "author", ""),
                     "status": getattr(r, "status", None),
                     "assumptions": len(getattr(r, "assumptions", []) or [])} for r in recs],
    }


@app.get("/api/evaluation")
async def evaluation():
    """Evaluation page: benchmark, real-data track, and performance results (whatever has been produced)."""
    res = ROOT / "evaluation" / "results"
    bench = _json(res / "results.json")
    cases = _json(ROOT / "evaluation" / "cases.json")
    return {"benchmark": bench, "cases": cases, "real": _json(res / "real_govuk.json"),
            "real_runs": _json(res / "real_govuk_runs.json"), "perf": _json(res / "perf.json")}


@app.post("/api/demo/reset")
async def demo_reset():
    from scripts.seed import seed
    await seed()
    return {"records": len(store.all())}


if (WEB / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")


@app.get("/")
async def index():
    if not (WEB / "index.html").exists():
        return JSONResponse(status_code=503, content={"detail": "UI not built: run `npm install && npm run build` in web/"})
    return FileResponse(WEB / "index.html")
