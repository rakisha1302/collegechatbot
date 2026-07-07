"""
LangSmith configuration for tracing, debugging, monitoring and evaluation
of every LangChain chain invocation in this application.

LangSmith works transparently through environment variables that LangChain
reads at runtime (LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT,
LANGCHAIN_ENDPOINT). This module also exposes a thin wrapper client so the
admin dashboard can pull run statistics (latency, error rate, provider
comparison) directly from LangSmith.
"""
import os
from utils.logger import get_logger

logger = get_logger(__name__)

_client = None


def get_langsmith_client():
    """Lazily instantiate and cache the LangSmith client, if configured."""
    global _client
    if _client is not None:
        return _client

    if not os.getenv("LANGCHAIN_API_KEY"):
        logger.warning("LANGCHAIN_API_KEY not set - LangSmith tracing is disabled.")
        return None

    try:
        from langsmith import Client
        _client = Client(
            api_url=os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
            api_key=os.getenv("LANGCHAIN_API_KEY"),
        )
        logger.info("LangSmith client initialized for project '%s'.",
                    os.getenv("LANGCHAIN_PROJECT"))
        return _client
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to initialize LangSmith client: %s", exc)
        return None


def fetch_recent_runs(limit: int = 50, project_name: str | None = None) -> list[dict]:
    """
    Pull recent run traces from LangSmith for the admin analytics dashboard.
    Returns a list of dicts with id, name, status, latency, provider tags, and errors.
    Fails gracefully (returns []) if LangSmith is not configured or unreachable.
    """
    client = get_langsmith_client()
    if client is None:
        return []

    project = project_name or os.getenv("LANGCHAIN_PROJECT", "college-chatbot")
    runs = []
    try:
        for run in client.list_runs(project_name=project, limit=limit):
            latency = None
            if run.end_time and run.start_time:
                latency = (run.end_time - run.start_time).total_seconds() * 1000
            runs.append({
                "id": str(run.id),
                "name": run.name,
                "status": run.status,
                "latency_ms": latency,
                "error": run.error,
                "start_time": run.start_time.isoformat() if run.start_time else None,
            })
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Error fetching LangSmith runs: %s", exc)
        return []

    return runs
