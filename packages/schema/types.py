from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    expected: str | None = None
    value: Any | None = None

    def __str__(self) -> str:
        prefix = self.path or "$"
        if self.expected:
            return f"{prefix}: {self.message} (expected {self.expected})"
        return f"{prefix}: {self.message}"


class SchemaValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        return "; ".join(str(issue) for issue in self.issues)
