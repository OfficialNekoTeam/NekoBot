from __future__ import annotations

from typing import Any

from .fields import ObjectSchema
from .types import SchemaValidationError


class SchemaRegistry:
    def __init__(self) -> None:
        self._schemas: dict[str, ObjectSchema] = {}

    def register(self, name: str, schema: ObjectSchema) -> None:
        if name in self._schemas:
            raise ValueError(f"schema already registered: {name}")
        self._schemas[name] = schema

    def get(self, name: str) -> ObjectSchema:
        try:
            return self._schemas[name]
        except KeyError as exc:
            raise KeyError(f"schema not found: {name}") from exc

    def has(self, name: str) -> bool:
        return name in self._schemas

    def validate(self, name: str, payload: dict[str, Any]) -> None:
        schema = self.get(name)
        issues = schema.validate(payload)
        if issues:
            raise SchemaValidationError(issues)

    def list(self) -> tuple[str, ...]:
        return tuple(sorted(self._schemas.keys()))
