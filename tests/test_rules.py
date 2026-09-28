"""Unit tests for the deterministic rules (methodology §5). No network."""
from datetime import date
from itertools import product

from src import rules
from src.schema import AssumptionCheck, Status, Verdict

H, U, B = Status.HOLDS, Status.UNKNOWN, Status.BROKEN
RANK = {H: 0, U: 1, B: 2}
VRANK = {Verdict.REUSE: 0, Verdict.ADAPT: 1, Verdict.RECONSIDER: 2}


def chk(i, status, critical=True, ev=()):
    return AssumptionCheck(assumption_id=f"A{i}", statement="s", critical=critical, status=status, evidence_ids=list(ev))


def test_verdict_rows():
    assert rules.verdict([], False, has_precedent=False) == Verdict.INSUFFICIENT_EVIDENCE
    assert rules.verdict([chk(1, H), chk(2, H, False)], False) == Verdict.REUSE
    assert rules.verdict([chk(1, H), chk(2, B, False)], False) == Verdict.ADAPT
    assert rules.verdict([chk(1, U), chk(2, H, False)], False) == Verdict.ADAPT
    assert rules.verdict([chk(1, B), chk(2, H, False)], False) == Verdict.RECONSIDER
    assert rules.verdict([chk(1, H)], precedent_failed=True) == Verdict.RECONSIDER


def test_monotonic_in_contradiction_exhaustive():
    """Property 1: raising any assumption's status (H < U < B) or setting failure never lowers the verdict."""
    crit = [True, True, False]
    states = list(product([H, U, B], repeat=3))
    for s in states:
        for s2 in states:
            if not all(RANK[a] <= RANK[b] for a, b in zip(s, s2)):
                continue
            for f, f2 in [(False, False), (False, True), (True, True)]:
                v = rules.verdict([chk(i, x, c) for i, (x, c) in enumerate(zip(s, crit))], f)
                v2 = rules.verdict([chk(i, x, c) for i, (x, c) in enumerate(zip(s2, crit))], f2)
                assert VRANK[v2] >= VRANK[v], (s, s2, f, f2)


def test_fail_safe_never_reuse():
    """Property 3: if the judge fails every status is UNKNOWN; with any critical assumption the verdict is not REUSE."""
    assert rules.verdict([chk(1, U), chk(2, U, False)], False) == Verdict.ADAPT
    # regression: all assumptions non-critical and the judge failed → still not REUSE
    assert rules.verdict([chk(1, U, False), chk(2, U, False)], False, evaluation_complete=False) == Verdict.ADAPT


def test_grounding_drops_hallucinated_citations():
    checks, warnings = rules.ground([chk(1, B, ev=["SIG-1", "SIG-FAKE"])], {"SIG-1"})
    assert checks[0].status == B and checks[0].evidence_ids == ["SIG-1"] and checks[0].basis == "contradicted"
    assert any("SIG-FAKE" in w for w in warnings)


def test_grounding_downgrades_broken_without_evidence():
    checks, warnings = rules.ground([chk(1, B, ev=["NOPE"])], {"SIG-1", "USER"})
    assert checks[0].status == U and checks[0].basis == "ambiguous"
    assert any("downgraded" in w for w in warnings)


def test_grounding_basis_for_holds():
    confirmed, _ = rules.ground([chk(1, H, ev=["SIG-1"])], {"SIG-1"})
    unchallenged, _ = rules.ground([chk(1, H)], {"SIG-1"})
    assert confirmed[0].basis == "confirmed" and unchallenged[0].basis == "no_change_recorded"


def test_every_warning_has_a_witness():
    """Property 2: after grounding, every BROKEN assumption cites at least one provided evidence ID."""
    checks, _ = rules.ground([chk(1, B, ev=["X"]), chk(2, B, ev=["SIG-1"]), chk(3, B)], {"SIG-1"})
    assert all(c.evidence_ids for c in checks if c.status == B)


def test_health():
    assert rules.health([]) is None
    assert rules.health([chk(1, H), chk(2, H, False)]) == 1.0
    assert rules.health([chk(1, B), chk(2, B), chk(3, H, False)]) == 0.2  # worked example §11.5
    assert rules.health([chk(1, U), chk(2, H), chk(3, H, False)]) == 0.8


def test_reciprocal_rank_matches_worked_example():
    s = rules.reciprocal_rank_scores(["ADR-007", "ADR-007", "ADR-031", "ADR-007", "ADR-015", "ADR-031", "ADR-021", "ADR-007"])
    assert round(s["ADR-007"], 4) == 1.1444 and round(s["ADR-031"], 4) == 0.3929


def test_admissible_and_age():
    assert rules.admissible(date(2025, 8, 14), date(2023, 2, 14))
    assert not rules.admissible(date(2022, 11, 3), date(2023, 2, 14))
    assert rules.age(date(2023, 2, 14), date(2026, 9, 28)) == "3 years 7 months ago"
    assert rules.age(date(2026, 9, 1), date(2026, 9, 28)) == "less than a month ago"
