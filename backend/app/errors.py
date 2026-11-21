"""Structured errors and diagnostics shared by the analysis pipeline and the HTTP layer.

Two kinds of problems are reported to the frontend:

* ``AnalysisError`` – the whole analysis cannot continue (bad URL, repo not found,
  GitHub rate limit, ...). It becomes an HTTP error whose JSON body carries a stable
  machine-readable ``error.code`` next to the human-readable ``detail``.
* ``Diagnostic`` – something went wrong (or is worth knowing) *inside* an otherwise
  successful analysis: a lockfile that could not be parsed, dependencies that could not
  be resolved, advisories whose details could not be fetched. They are returned in
  ``analysis_metadata.diagnostics`` so the UI can show exactly what is missing and why.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SEVERITIES = ("error", "warning", "info")


@dataclass
class Diagnostic:
    code: str
    severity: str
    message: str
    path: str | None = None
    hint: str | None = None
    details: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"code": self.code, "severity": self.severity, "message": self.message}
        if self.path is not None:
            data["path"] = self.path
        if self.hint:
            data["hint"] = self.hint
        if self.details:
            data["details"] = self.details
        return data


class AnalysisError(ValueError):
    """A fatal, user-explainable analysis failure.

    Subclasses ``ValueError`` so older callers that catch ``ValueError`` keep working.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 422,
        hint: str | None = None,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.hint = hint
        self.retryable = retryable
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "retryable": self.retryable,
            "details": self.details,
        }


class LockfileError(ValueError):
    """A lockfile that cannot be turned into a trustworthy graph."""

    def __init__(self, code: str, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.hint = hint


@dataclass
class DiagnosticList:
    """Small helper so loaders can append without caring about the wire format."""

    items: list[Diagnostic] = field(default_factory=list)

    def add(self, code: str, severity: str, message: str, **kwargs: Any) -> Diagnostic:
        diagnostic = Diagnostic(code, severity, message, **kwargs)
        self.items.append(diagnostic)
        return diagnostic
