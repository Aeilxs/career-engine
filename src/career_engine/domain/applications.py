"""Application stage rules available before package approval and submission exist.

Only stages that need no package, approval or ATS submission are reachable in J1. Reaching
APPROVED, SUBMITTING or SUBMITTED requires the J4-J6 gates and is deliberately not offered.
"""

from career_engine.domain.errors import InvalidTransition

INITIAL_STAGE = "DRAFT"
J1_STAGES = ("DRAFT", "PREPARING", "BLOCKED")
_ALLOWED: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"PREPARING", "BLOCKED"}),
    "PREPARING": frozenset({"DRAFT", "BLOCKED"}),
    "BLOCKED": frozenset({"DRAFT", "PREPARING"}),
}


def check_transition(from_stage: str, to_stage: str) -> None:
    if to_stage not in J1_STAGES:
        raise InvalidTransition(f"Stage {to_stage} cannot be set at this milestone.")
    if to_stage not in _ALLOWED.get(from_stage, frozenset()):
        raise InvalidTransition(f"Transition {from_stage} -> {to_stage} is not allowed.")
