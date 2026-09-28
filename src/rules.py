"""Deterministic decision rules (methodology §5). Pure functions — no I/O, no LLM.

The LLM only judges each assumption locally; everything that determines the
verdict lives here, so it can be unit-tested and audited.
"""
from __future__ import annotations

from datetime import date

from .schema import AssumptionCheck, Status, Verdict

_ORDER = {Verdict.REUSE: 0, Verdict.ADAPT: 1, Verdict.RECONSIDER: 2}


def verdict(checks: list[AssumptionCheck], precedent_failed: bool, has_precedent: bool = True,
            evaluation_complete: bool = True) -> Verdict:
    """Definition 4. Monotone in contradiction: raising any status (H < U < B) never lowers the verdict.

    Fail-safe: if the assumptions could not be evaluated (judge failure), the verdict is never REUSE,
    even when no assumption is marked critical.
    """
    if not has_precedent:
        return Verdict.INSUFFICIENT_EVIDENCE
    if precedent_failed or any(c.critical and c.status == Status.BROKEN for c in checks):
        return Verdict.RECONSIDER
    if not evaluation_complete or any((not c.critical and c.status == Status.BROKEN)
                                      or (c.critical and c.status == Status.UNKNOWN) for c in checks):
        return Verdict.ADAPT
    return Verdict.REUSE


def explain(checks: list[AssumptionCheck], failures: list[str], evaluation_complete: bool = True) -> str:
    """Which rule of Definition 4 fired, in words (shown in the orchestration view)."""
    crit_broken = [c.assumption_id for c in checks if c.critical and c.status == Status.BROKEN]
    if failures or crit_broken:
        why = ([f"critical {', '.join(crit_broken)} BROKEN"] if crit_broken else []) + \
              ([f"{', '.join(failures)} records this approach failing"] if failures else [])
        return " and ".join(why) + " → RECONSIDER"
    if not evaluation_complete:
        return "assumptions could not be evaluated → ADAPT (never REUSE on failure)"
    minor_broken = [c.assumption_id for c in checks if not c.critical and c.status == Status.BROKEN]
    crit_unknown = [c.assumption_id for c in checks if c.critical and c.status == Status.UNKNOWN]
    if minor_broken or crit_unknown:
        why = ([f"non-critical {', '.join(minor_broken)} BROKEN"] if minor_broken else []) + \
              ([f"critical {', '.join(crit_unknown)} UNKNOWN"] if crit_unknown else [])
        return " and ".join(why) + " → ADAPT"
    return "every assumption holds and no recorded failure → REUSE"


def ground(checks: list[AssumptionCheck], provided_ids: set[str]) -> tuple[list[AssumptionCheck], list[str]]:
    """§5.4: drop citations that were never provided; BROKEN without valid evidence → UNKNOWN."""
    out, warnings = [], []
    for c in checks:
        valid = [e for e in c.evidence_ids if e in provided_ids]
        dropped = [e for e in c.evidence_ids if e not in provided_ids]
        if dropped:
            warnings.append(f"{c.assumption_id}: removed citation(s) not in evidence: {', '.join(dropped)}")
        status, basis = c.status, c.basis
        if status == Status.BROKEN and not valid:
            status, basis = Status.UNKNOWN, "ambiguous"
            warnings.append(f"{c.assumption_id}: BROKEN without valid evidence, downgraded to UNKNOWN")
        elif status == Status.BROKEN:
            basis = "contradicted"
        elif status == Status.HOLDS:
            basis = "confirmed" if valid else "no_change_recorded"
        else:
            basis = "ambiguous"
        out.append(c.model_copy(update={"evidence_ids": valid, "status": status, "basis": basis}))
    return out, warnings


def settle_uncited_unknowns(checks: list[AssumptionCheck], provided_ids: set[str],
                            judged_ids: set[str]) -> tuple[list[AssumptionCheck], list[str]]:
    """The judge's protocol: UNKNOWN means evidence addresses the assumption but is ambiguous; no evidence at all
    means HOLDS. A judged UNKNOWN that cites no provided evidence is therefore "no change recorded".
    Only assumptions the judge actually returned are settled, so a failed or omitted judgement stays UNKNOWN
    (fail-safe), and this runs before ground(), so a BROKEN claim without evidence still becomes UNKNOWN."""
    out, warnings = [], []
    for c in checks:
        if (c.assumption_id in judged_ids and c.status == Status.UNKNOWN
                and not any(e in provided_ids for e in c.evidence_ids)):
            warnings.append(f"{c.assumption_id}: UNKNOWN with no cited evidence, treated as no change recorded")
            c = c.model_copy(update={"status": Status.HOLDS, "evidence_ids": []})
        out.append(c)
    return out, warnings


def health(checks: list[AssumptionCheck]) -> float | None:
    """Display-only gauge (§5.7): critical weight 2, other 1; UNKNOWN counts half."""
    if not checks:
        return None
    w = [2 if c.critical else 1 for c in checks]
    penalty = sum(wi * (1.0 if c.status == Status.BROKEN else 0.5 if c.status == Status.UNKNOWN else 0.0)
                  for wi, c in zip(w, checks))
    return round(1 - penalty / sum(w), 2)


def reciprocal_rank_scores(doc_ids: list[str | None], k0: int = 1) -> dict[str, float]:
    """§6.2: S(D) = sum over facts from D of 1 / (k0 + rank)."""
    scores: dict[str, float] = {}
    for j, d in enumerate(doc_ids, start=1):
        if d:
            scores[d] = scores.get(d, 0.0) + 1.0 / (k0 + j)
    return scores


def admissible(evidence_date: date, decision_date: date) -> bool:
    """§5.2: only evidence dated after the decision can invalidate it."""
    return evidence_date > decision_date


def age(then: date, now: date) -> str:
    months = (now.year - then.year) * 12 + (now.month - then.month) - (1 if now.day < then.day else 0)
    y, m = divmod(max(months, 0), 12)
    parts = ([f"{y} year{'s' if y != 1 else ''}"] if y else []) + ([f"{m} month{'s' if m != 1 else ''}"] if m else [])
    return (" ".join(parts) or "less than a month") + " ago"
