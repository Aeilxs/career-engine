"""Single durable job-claim step. J1 registers no job kinds; unknown kinds are BLOCKED."""

from collections.abc import Callable, Mapping
from typing import Any

from career_engine.infrastructure.jobs import JobQueue

Handler = Callable[[dict[str, Any]], dict[str, Any]]


def run_once(queue: JobQueue, handlers: Mapping[str, Handler], lease_seconds: int = 60) -> str:
    """Claim and process at most one job. Returns the observed outcome label."""
    job = queue.claim(lease_seconds)
    if job is None:
        return "IDLE"
    handler = handlers.get(job.kind)
    if handler is None:
        queue.block(job.id, job.generation, "UNKNOWN_JOB_KIND")
        return "BLOCKED"
    try:
        result = handler(job.payload)
    except Exception as error:
        queue.fail(job.id, job.generation, type(error).__name__, retryable=True)
        return "FAILED_OR_REQUEUED"
    return "SUCCEEDED" if queue.complete(job.id, job.generation, result) else "STALE_WORKER"
