"""Markdown → canonical records.

ADRs are written the way real teams write them: prose, no assumptions list.
`extract_assumptions` recovers the implicit premises with an LLM and keeps only
those whose supporting quote appears verbatim in the source (quote-grounding).
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from .config import EXTRACTED, ROOT
from .llm import LLMError, complete_json
from .schema import Assumption, DecisionRecord, Postmortem, Signal


class IngestError(ValueError):
    pass


# ---------------------------------------------------------------- parsing

def parse_markdown(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text.strip() + "\n", re.S)
    if not m:
        raise IngestError("missing front matter (--- key: value --- block)")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, m.group(2).strip()


def sections(body: str) -> dict[str, str]:
    out, current = {}, "_intro"
    for line in body.splitlines():
        h = re.match(r"^##\s+(.*)", line)
        if h:
            current = h.group(1).strip().lower()
            out[current] = ""
        else:
            out[current] = out.get(current, "") + line + "\n"
    return {k: v.strip() for k, v in out.items()}


def _list(v: str) -> list[str]:
    return [x.strip() for x in v.split(",") if x.strip()]


def _date(meta: dict) -> date:
    try:
        return date.fromisoformat(meta["date"])
    except (KeyError, ValueError):
        raise IngestError("front matter needs date: YYYY-MM-DD")


def _require(meta: dict, *keys: str) -> None:
    missing = [k for k in keys if not meta.get(k)]
    if missing:
        raise IngestError(f"front matter missing: {', '.join(missing)}")


def parse_record(text: str, source_ref: str) -> DecisionRecord | Postmortem | Signal:
    meta, body = parse_markdown(text)
    _require(meta, "id", "title", "date")
    rid, d = meta["id"], _date(meta)
    sec = sections(body)
    kind = meta.get("kind") or ("adr" if rid.startswith("ADR-") else "postmortem" if rid.startswith("PM-")
                                else "signal" if rid.startswith("SIG-") else "")
    if kind == "adr":
        if "context" not in sec:
            raise IngestError("ADR is missing section '## Context'")
        outcome = sec.get("decision outcome") or sec.get("decision") or sec.get("proposal")  # MADR, Nygard, or proposal-style
        if not outcome:
            raise IngestError("ADR is missing section '## Decision Outcome' (or '## Decision')")
        chosen = re.search(r"Chosen option:\s*\*\*(.+?)\*\*", outcome)
        options = [re.sub(r"\*\*", "", o).strip() for o in re.findall(r"^\d+\.\s+(.*)$", sec.get("considered options", ""), re.M)]
        return DecisionRecord(
            id=rid, title=meta["title"], date=d, team=meta.get("team", ""), authors=_list(meta.get("authors", "")),
            status=meta.get("status", "accepted"), context=sec["context"], options=options,
            decision=chosen.group(1) if chosen else outcome.split("\n")[0],
            rationale=outcome, consequences=sec.get("consequences", ""), source_ref=source_ref,
        )
    if kind == "postmortem":
        return Postmortem(
            id=rid, title=meta["title"], date=d, severity=meta.get("severity", ""),
            authors=_list(meta.get("authors", "")), contributing_decisions=_list(meta.get("contributing_decisions", "")),
            summary=sec.get("summary", ""), root_cause=sec.get("root cause", ""), body=body, source_ref=source_ref,
        )
    if kind == "signal":
        return Signal(id=rid, title=meta["title"], date=d, author=meta.get("author", ""),
                      channel=meta.get("source", ""), body=body, source_ref=source_ref)
    raise IngestError(f"cannot tell what {rid} is: add 'kind: adr|postmortem|signal' or use an ADR-/PM-/SIG- id")


# ---------------------------------------------------------------- assumption extraction

EXTRACT_SYSTEM = """You read an architecture decision record and recover the ASSUMPTIONS the chosen option depends on:
conditions about the world at decision time that, if they stopped being true, would make the chosen option a worse choice.
They are usually stated implicitly in the Context: volumes and growth, latency figures, where customers are,
regions, contracts and compliance requirements, team skills and staffing, budgets, how external systems behave,
and who consumes the system and how.

Do NOT include:
- the motivation or problem being solved (e.g. "the old system is end-of-life", "incidents happened");
- requirements or goals the new system must meet (e.g. "we need SSO");
- reasons for rejecting the other options;
- consequences, costs or trade-offs accepted after the decision.

Rules:
- Each assumption needs a quote copied VERBATIM from the document. You may elide with "..." but every fragment must be verbatim.
- One assumption per distinct condition; do not duplicate.
- critical = true only if the chosen option would probably NOT have been chosen without it. Mark at most 2 as critical.
- Return 2 to 4 assumptions, most important first.
Return JSON: {"assumptions": [{"statement": "...", "critical": true, "quote": "..."}]}"""


class _Extracted(BaseModel):
    statement: str
    critical: bool = True
    quote: str


class _Extraction(BaseModel):
    assumptions: list[_Extracted]


_TYPO = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', " ": " ", " ": " ",
                       "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-"})


def _norm(s: str) -> str:
    s = s.translate(_TYPO).replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_in_source(quote: str, source: str) -> bool:
    """True if every ellipsis-separated fragment (>= 12 chars) appears verbatim in the source."""
    src = _norm(source)
    frags = [f.strip(" .,;") for f in re.split(r"\.\.\.|…", _norm(quote))]
    frags = [f for f in frags if f]
    return bool(frags) and all(len(f) >= 12 and f in src for f in frags)


async def extract_assumptions(rec: DecisionRecord, source_text: str, use_cache: bool = True,
                              cache_dir: Path = EXTRACTED) -> tuple[list[Assumption], list[str]]:
    """Returns (grounded assumptions, warnings). Cached per ADR for reproducibility."""
    cache = cache_dir / f"{rec.id}.json"
    if use_cache and cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        return [Assumption(**a) for a in data["assumptions"]], data.get("warnings", [])
    _, body = parse_markdown(source_text)
    try:
        out = await complete_json(EXTRACT_SYSTEM, f"ADR {rec.id}: {rec.title}\n\n{body}", _Extraction)
    except LLMError as e:
        return [], [f"assumption extraction failed: {e}"]
    kept, warnings = [], []
    for a in out.assumptions:
        if quote_in_source(a.quote, body):
            kept.append(Assumption(id=f"A{len(kept) + 1}", statement=a.statement, critical=a.critical,
                                   quote=a.quote, origin="extracted"))
        else:
            warnings.append(f"dropped ungrounded assumption: {a.statement!r} (quote: {a.quote[:120]!r})")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"assumptions": [a.model_dump() for a in kept], "warnings": warnings}, indent=2),
                     encoding="utf-8")
    return kept, warnings


def load_file(path: Path) -> tuple[str, str]:
    """Returns (text, repo-relative source_ref)."""
    return path.read_text(encoding="utf-8"), path.resolve().relative_to(ROOT).as_posix()
