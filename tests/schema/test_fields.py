from __future__ import annotations

import pytest

from packages.schema.fields import (
    BooleanField,
    IntegerField,
    ListField,
    ObjectSchema,
    StringField,
)
from packages.schema.registry import SchemaRegistry
from packages.schema.types import SchemaValidationError


# ---------------------------------------------------------------------------
# StringField
# ---------------------------------------------------------------------------

def test_string_field_accepts_valid_string() -> None:
    assert StringField().validate("hello") == []


def test_string_field_rejects_non_string() -> None:
    issues = StringField().validate(42)
    assert any("type" in i.message for i in issues)


def test_string_field_required_rejects_none() -> None:
    issues = StringField(required=True).validate(None)
    assert any("required" in i.message for i in issues)


def test_string_field_optional_accepts_none() -> None:
    assert StringField(required=False).validate(None) == []


def test_string_field_min_length() -> None:
    f = StringField(min_length=3)
    assert f.validate("abc") == []
    assert f.validate("ab") != []


def test_string_field_max_length() -> None:
    f = StringField(max_length=5)
    assert f.validate("hello") == []
    assert f.validate("toolong") != []


def test_string_field_choices() -> None:
    f = StringField(choices=("a", "b", "c"))
    assert f.validate("a") == []
    assert f.validate("z") != []


# ---------------------------------------------------------------------------
# IntegerField
# ---------------------------------------------------------------------------

def test_integer_field_accepts_int() -> None:
    assert IntegerField().validate(42) == []


def test_integer_field_rejects_string() -> None:
    assert IntegerField().validate("42") != []


def test_integer_field_rejects_bool() -> None:
    # bool is subclass of int — must be explicitly rejected
    assert IntegerField().validate(True) != []


def test_integer_field_minimum() -> None:
    f = IntegerField(minimum=0)
    assert f.validate(0) == []
    assert f.validate(-1) != []


def test_integer_field_maximum() -> None:
    f = IntegerField(maximum=100)
    assert f.validate(100) == []
    assert f.validate(101) != []


# ---------------------------------------------------------------------------
# BooleanField
# ---------------------------------------------------------------------------

def test_boolean_field_accepts_bool() -> None:
    assert BooleanField().validate(True) == []
    assert BooleanField().validate(False) == []


def test_boolean_field_rejects_int() -> None:
    assert BooleanField().validate(1) != []


def test_boolean_field_rejects_string() -> None:
    assert BooleanField().validate("true") != []


# ---------------------------------------------------------------------------
# ListField
# ---------------------------------------------------------------------------

def test_list_field_accepts_list() -> None:
    assert ListField().validate([]) == []
    assert ListField().validate([1, 2, 3]) == []


def test_list_field_rejects_non_list() -> None:
    assert ListField().validate("not-a-list") != []


def test_list_field_min_items() -> None:
    f = ListField(min_items=2)
    assert f.validate([1, 2]) == []
    assert f.validate([1]) != []


def test_list_field_max_items() -> None:
    f = ListField(max_items=2)
    assert f.validate([1, 2]) == []
    assert f.validate([1, 2, 3]) != []


def test_list_field_validates_items() -> None:
    f = ListField(item_field=StringField())
    assert f.validate(["a", "b"]) == []
    issues = f.validate(["a", 42])
    assert len(issues) == 1
    assert "[1]" in issues[0].path


# ---------------------------------------------------------------------------
# ObjectSchema
# ---------------------------------------------------------------------------

def test_object_schema_validates_required_fields() -> None:
    schema = ObjectSchema(fields={"name": StringField(), "age": IntegerField()})
    assert schema.validate({"name": "Alice", "age": 30}) == []


def test_object_schema_reports_missing_required_field() -> None:
    schema = ObjectSchema(fields={"name": StringField()})
    issues = schema.validate({})
    assert any("missing" in i.message for i in issues)


def test_object_schema_reports_extra_fields_by_default() -> None:
    schema = ObjectSchema(fields={"name": StringField()})
    issues = schema.validate({"name": "x", "extra": "y"})
    assert any("not declared" in i.message for i in issues)


def test_object_schema_allow_extra_suppresses_extra_field_error() -> None:
    schema = ObjectSchema(fields={"name": StringField()}, allow_extra=True)
    assert schema.validate({"name": "x", "extra": "y"}) == []


def test_object_schema_rejects_non_dict() -> None:
    schema = ObjectSchema(fields={})
    issues = schema.validate("not-a-dict")  # type: ignore[arg-type]
    assert any("type" in i.message for i in issues)


def test_object_schema_path_prefix_in_nested_error() -> None:
    schema = ObjectSchema(fields={"key": StringField(min_length=5)})
    issues = schema.validate({"key": "ab"})
    assert issues[0].path == "key"


# ---------------------------------------------------------------------------
# SchemaRegistry
# ---------------------------------------------------------------------------

def test_schema_registry_register_and_get() -> None:
    reg = SchemaRegistry()
    schema = ObjectSchema(fields={"x": StringField()})
    reg.register("test", schema)
    assert reg.get("test") is schema


def test_schema_registry_has() -> None:
    reg = SchemaRegistry()
    reg.register("s", ObjectSchema(fields={}))
    assert reg.has("s") is True
    assert reg.has("missing") is False


def test_schema_registry_duplicate_raises() -> None:
    reg = SchemaRegistry()
    reg.register("s", ObjectSchema(fields={}))
    with pytest.raises(ValueError, match="already registered"):
        reg.register("s", ObjectSchema(fields={}))


def test_schema_registry_get_missing_raises() -> None:
    reg = SchemaRegistry()
    with pytest.raises(KeyError):
        reg.get("nope")


def test_schema_registry_validate_passes() -> None:
    reg = SchemaRegistry()
    reg.register("cfg", ObjectSchema(fields={"key": StringField()}))
    reg.validate("cfg", {"key": "value"})  # must not raise


def test_schema_registry_validate_raises_on_error() -> None:
    reg = SchemaRegistry()
    reg.register("cfg", ObjectSchema(fields={"key": StringField()}))
    with pytest.raises(SchemaValidationError):
        reg.validate("cfg", {})


def test_schema_registry_list_sorted() -> None:
    reg = SchemaRegistry()
    reg.register("z", ObjectSchema(fields={}))
    reg.register("a", ObjectSchema(fields={}))
    assert reg.list() == ("a", "z")
