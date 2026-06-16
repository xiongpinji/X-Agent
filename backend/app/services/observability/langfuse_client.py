from __future__ import annotations

import logging
from typing import Any

from backend.app.services.observability.event_exporter import observability_exporter
from backend.app.settings import get_settings

try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover - optional runtime dependency
    Langfuse = None  # type: ignore[assignment]


class LangfuseClient:
    """Langfuse-backed observability facade with in-memory fallback."""

    _logger = logging.getLogger("xagent.observability.langfuse")

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
            self._log_to_real_client(event_type, event, payload)
        return event

    def _log_to_real_client(self, event_type: str, event: Any, payload: dict[str, Any]) -> None:
        """Send an event to whichever Langfuse SDK surface is installed.

        Observability must never break the agent execution path. Langfuse v2
        exposed ``trace(...).event(...)`` while newer SDKs expose
        ``create_event(...)``. Support both and degrade to the local exporter
        if the configured client cannot accept the event.
        """
        metadata = {
            **event.payload,
            "tenant_id": event.tenant_id,
            "user_id": event.user_id,
            "run_id": event.run_id,
            "workflow_id": event.workflow_id,
            "agent_id": event.agent_id,
        }
        trace_id = event.trace_id or payload.get("trace_id")

        try:
            if hasattr(self._client, "trace"):
                trace = self._client.trace(id=trace_id)
                trace.event(name=event_type, metadata=metadata)
                return

            if hasattr(self._client, "create_event"):
                trace_context = {"trace_id": trace_id} if trace_id else None
                self._client.create_event(
                    trace_context=trace_context,
                    name=event_type,
                    metadata=metadata,
                )
                return

            self._logger.warning(
                "Configured Langfuse client has no supported event API; using local exporter only."
            )
        except Exception as exc:  # pragma: no cover - depends on external SDK/network behavior
            self._logger.warning(
                "Langfuse event export failed; using local exporter only: %s",
                exc,
            )

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
