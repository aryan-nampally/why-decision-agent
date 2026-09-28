"""Import GOV.UK's real architecture decision records (alphagov/govuk-aws, MIT licence).

    python -m scripts.import_govuk

Downloads docs/architecture/decisions/*.md, converts each to WHY's front-matter format
using the date written inside the ADR, and writes data/real/govuk-aws/.

Leakage control: older ADRs were later annotated with "Superseded by ..." lines. Those
annotations would hand the answer to the evaluator, so they are removed; the superseding
ADRs themselves are kept unchanged — they are the real later evidence.
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from src.config import DATA

REPO = "alphagov/govuk-aws"
PATH = "docs/architecture/decisions"
OUT = DATA / "real" / "govuk-aws"
NOTICE = f"""Source: https://github.com/{REPO}/tree/master/{PATH}
Licence: MIT (Copyright (c) Crown Copyright (Government Digital Service)).
These are real architecture decision records published by GOV.UK. They were converted to WHY's
front-matter format; 'Superseded by' annotations added to older records after the fact were
removed so that evaluation cannot read the answer from the record being evaluated.
"""


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "why-agent-importer"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


STATUSES: dict[str, str] = {}  # original statuses, kept out of the ingested text (provenance only)


def convert(name: str, text: str) -> str | None:
    num = re.match(r"(\d{4})-", name)
    date = re.search(r"^Date:\s*(\d{4}-\d{2}-\d{2})", text, re.M)
    title = re.search(r"^#\s+(?:\d+\.\s*)?(.+)$", text, re.M)
    if not (num and date and title):
        return None
    status = re.search(r"^## Status\s*\n+(.+?)\n", text, re.M)
    body = re.sub(r"^#\s+.*\n", "", text, count=1, flags=re.M)
    body = re.sub(r"^Date:.*\n", "", body, flags=re.M)
    body = re.sub(r"^## Status\s*\n+.*?\n(?=## )", "", body, flags=re.M | re.S)
    body = "\n".join(l for l in body.splitlines() if not re.search(r"superseded by", l, re.I))
    rid = f"GOVUK-{num.group(1)}"
    STATUSES[rid] = status.group(1).strip() if status else "unknown"
    return (f"---\nid: {rid}\nkind: adr\ntitle: {title.group(1).strip()}\ndate: {date.group(1)}\nteam: GOV.UK Platform\n"
            f"authors: GOV.UK Technical Operations\nstatus: accepted\n"
            f"source: https://github.com/{REPO}/blob/master/{PATH}/{name}\n---\n\n"
            f"# {rid}: {title.group(1).strip()}\n\n{body.strip()}\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    listing = json.loads(fetch(f"https://api.github.com/repos/{REPO}/contents/{PATH}"))
    n = 0
    for item in listing:
        if not item["name"].endswith(".md") or not item["name"][:4].isdigit():
            continue
        md = convert(item["name"], fetch(item["download_url"]).decode("utf-8"))
        if md:
            (OUT / f"GOVUK-{item['name'][:4]}.md").write_text(md, encoding="utf-8")
            n += 1
    (OUT / "NOTICE.md").write_text(NOTICE, encoding="utf-8")
    (OUT.parent / "govuk-original-status.json").write_text(json.dumps(STATUSES, indent=2), encoding="utf-8")
    print(f"imported {n} ADRs into {OUT}")


if __name__ == "__main__":
    main()
