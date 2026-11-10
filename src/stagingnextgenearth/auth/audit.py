"""Structured audit events for identity operations."""

from dataclasses import dataclass
from typing import Protocol

import structlog


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Security-relevant identity operation outcome."""

    action: str
    outcome: str
    subject: str | None = None


class AuditSink(Protocol):
    """Destination for structured identity audit events."""

    def emit(self, event: AuditEvent) -> None:
        """Record an audit event."""


class StructuredAuditSink:
    """Emit audit events through the configured structured logging pipeline."""

    def __init__(self) -> None:
        self._logger = structlog.get_logger("stagingnextgenearth.audit")

    def emit(self, event: AuditEvent) -> None:
        """Write an audit event without credentials or token material."""
        self._logger.info(
            "identity_audit",
            audit_action=event.action,
            audit_outcome=event.outcome,
            **({"subject": event.subject} if event.subject is not None else {}),
        )


class NullAuditSink:
    """No-op audit sink for callers that explicitly disable audit emission."""

    def emit(self, event: AuditEvent) -> None:
        """Discard the event."""
        return None
