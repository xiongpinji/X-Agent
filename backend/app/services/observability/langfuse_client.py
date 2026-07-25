from __future__ import annotations

from typing import Any

from backend.app.services.observability.event_exporter import observability_exporter
from backend.app.settings import get_settings

try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover - optional runtime dependency
    Langfuse = None  # type: ignore[assignment]


class LangfuseClient:
    """Langfuse-backed observability facade with in-memory fallback."""

    def __init__(
        self,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str | None = None,
    ) -> None:
        """Initialize Langfuse client with optional credentials.

        Args:
            public_key: Langfuse public key
            secret_key: Langfuse secret key
            host: Langfuse host URL
        """
        self._client = (
            Langfuse(public_key=public_key, secret_key=secret_key, host=host)
            if Langfuse is not None and public_key and secret_key
            else None
        )

    @property
    def has_real_client(self) -> bool:
        return self._client is not None

    def log(self, event_type: str, **payload) -> Any:
        """Log an event to Langfuse with fallback to in-memory storage.

        Args:
            event_type: Type of event to log
            **payload: Event payload data

        Returns:
            The exported event object
        """
        event = observability_exporter.export(event_type, **payload)
        if self._client is not None:
            try:
                trace = self._client.trace(id=event.trace_id or payload.get("trace_id"))
                trace.event(
                    name=event_type,
                    metadata={
                        **event.payload,
                        "tenant_id": event.tenant_id,
                        "user_id": event.user_id,
                        "run_id": event.run_id,
                        "workflow_id": event.workflow_id,
                        "agent_id": event.agent_id,
                    },
                )
            except (AttributeError, TypeError, Exception):
                # Langfuse client may not have trace method in test/mock environments
                # or may fail due to network issues - gracefully degrade to in-memory only
                pass
        return event

    def events(self) -> list[Any]:
        """Get all logged events.

        Returns:
            List of all events in the exporter
        """
        return observability_exporter.list_events()


settings = get_settings()
langfuse_client = LangfuseClient(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host,
)
