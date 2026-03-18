from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import ValidationIssue


def _join_path(parent: str, child: str) -> str:
    if not parent:
        return child
    if child.startswith("["):
        return f"{parent}{child}"
    return f"{parent}.{child}"


@dataclass(frozen=True)
class Field:
    required: bool = True
    default: Any = None
    choices: tuple[Any, ...] = ()
    description: str = ""

    def validate(self, value: Any, path: str = "") -> list[ValidationIssue]:
        if value is None:
            if self.required:
                return [ValidationIssue(path=path, message="value is required")]
            return []

        issues = self._validate_type(value, path)
        if issues:
            return issues

        if self.choices and value not in self.choices:
            return [
                ValidationIssue(
                    path=path,
                    message="value is not in allowed choices",
                    expected=", ".join(str(choice) for choice in self.choices),
                    value=value,
                )
            ]

        return []

    def _validate_type(self, value: Any, path: str) -> list[ValidationIssue]:
        return []


@dataclass(frozen=True)
class StringField(Field):
    min_length: int | None = None
    max_length: int | None = None

    def _validate_type(self, value: Any, path: str) -> list[ValidationIssue]:
        if not isinstance(value, str):
            return [
                ValidationIssue(
                    path=path, message="invalid type", expected="str", value=value
                )
            ]

        issues: list[ValidationIssue] = []
        if self.min_length is not None and len(value) < self.min_length:
            issues.append(
                ValidationIssue(
                    path=path, message="string is shorter than minimum length"
                )
            )
        if self.max_length is not None and len(value) > self.max_length:
            issues.append(
                ValidationIssue(
                    path=path, message="string is longer than maximum length"
                )
            )
        return issues


@dataclass(frozen=True)
class IntegerField(Field):
    minimum: int | None = None
    maximum: int | None = None

    def _validate_type(self, value: Any, path: str) -> list[ValidationIssue]:
        if isinstance(value, bool) or not isinstance(value, int):
            return [
                ValidationIssue(
                    path=path, message="invalid type", expected="int", value=value
                )
            ]

        issues: list[ValidationIssue] = []
        if self.minimum is not None and value < self.minimum:
            issues.append(ValidationIssue(path=path, message="value is below minimum"))
        if self.maximum is not None and value > self.maximum:
            issues.append(ValidationIssue(path=path, message="value is above maximum"))
        return issues


@dataclass(frozen=True)
class BooleanField(Field):
    def _validate_type(self, value: Any, path: str) -> list[ValidationIssue]:
        if not isinstance(value, bool):
            return [
                ValidationIssue(
                    path=path, message="invalid type", expected="bool", value=value
                )
            ]
        return []


@dataclass(frozen=True)
class ListField(Field):
    item_field: Field = field(default_factory=Field)
    min_items: int | None = None
    max_items: int | None = None

    def _validate_type(self, value: Any, path: str) -> list[ValidationIssue]:
        if not isinstance(value, list):
            return [
                ValidationIssue(
                    path=path, message="invalid type", expected="list", value=value
                )
            ]

        issues: list[ValidationIssue] = []
        if self.min_items is not None and len(value) < self.min_items:
            issues.append(ValidationIssue(path=path, message="list has too few items"))
        if self.max_items is not None and len(value) > self.max_items:
            issues.append(ValidationIssue(path=path, message="list has too many items"))

        for index, item in enumerate(value):
            issues.extend(
                self.item_field.validate(item, _join_path(path, f"[{index}]"))
            )

        return issues


@dataclass(frozen=True)
class ObjectSchema:
    fields: dict[str, Field]
    allow_extra: bool = False
    description: str = ""

    def validate(self, payload: dict[str, Any]) -> list[ValidationIssue]:
        if not isinstance(payload, dict):
            return [
                ValidationIssue(
                    path="", message="invalid type", expected="object", value=payload
                )
            ]

        issues: list[ValidationIssue] = []

        for field_name, field_def in self.fields.items():
            if field_name not in payload:
                if field_def.required:
                    issues.append(
                        ValidationIssue(
                            path=field_name, message="missing required field"
                        )
                    )
                continue
            issues.extend(field_def.validate(payload[field_name], field_name))

        if not self.allow_extra:
            allowed = set(self.fields.keys())
            for key in payload:
                if key not in allowed:
                    issues.append(
                        ValidationIssue(
                            path=key, message="field is not declared in schema"
                        )
                    )

        return issues
