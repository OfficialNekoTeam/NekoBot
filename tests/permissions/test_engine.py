from __future__ import annotations

import pytest

from packages.permissions.engine import PermissionEngine
from packages.permissions.models import (
    AuthorizationContext,
    PermissionRule,
    ResourceRef,
    Subject,
)


def _ctx(
    *,
    roles: tuple[str, ...] = (),
    group_roles: tuple[str, ...] = (),
    scope: str = "global",
    platform: str | None = None,
    resource_kind: str = "command",
    resource_name: str = "test",
) -> AuthorizationContext:
    return AuthorizationContext(
        subject=Subject(actor_id="user-1", roles=roles, group_roles=group_roles),
        resource=ResourceRef(kind=resource_kind, name=resource_name),
        scope=scope,
        platform=platform,
    )


def _rule(
    permissions: tuple[str, ...] = ("cmd.run",),
    roles: tuple[str, ...] = (),
    allow: bool = True,
    require_all: bool = False,
) -> PermissionRule:
    return PermissionRule(permissions=permissions, roles=roles, allow=allow, require_all=require_all)


# ---------------------------------------------------------------------------
# Empty engine / no permissions
# ---------------------------------------------------------------------------

def test_no_permissions_requested_always_allowed() -> None:
    engine = PermissionEngine()
    assert engine.check((), _ctx()) is True


def test_no_rules_denies_any_permission() -> None:
    engine = PermissionEngine()
    assert engine.check(("cmd.run",), _ctx()) is False


# ---------------------------------------------------------------------------
# Owner / super_admin bypass
# ---------------------------------------------------------------------------

def test_owner_role_bypasses_all_rules() -> None:
    engine = PermissionEngine()  # no rules at all
    assert engine.check(("cmd.run",), _ctx(roles=("owner",))) is True


def test_super_admin_bypasses_all_rules() -> None:
    engine = PermissionEngine()
    assert engine.check(("anything",), _ctx(roles=("super_admin",))) is True


def test_non_elevated_role_does_not_bypass() -> None:
    engine = PermissionEngine()
    assert engine.check(("cmd.run",), _ctx(roles=("admin",))) is False


# ---------------------------------------------------------------------------
# Allow rules
# ---------------------------------------------------------------------------

def test_allow_rule_grants_permission() -> None:
    engine = PermissionEngine((_rule(permissions=("cmd.run",), roles=("admin",)),))
    assert engine.check(("cmd.run",), _ctx(roles=("admin",))) is True


def test_rule_without_role_restriction_grants_to_all() -> None:
    engine = PermissionEngine((_rule(permissions=("provider.use",), roles=()),))
    assert engine.check(("provider.use",), _ctx()) is True


def test_require_all_false_allows_if_any_permission_matched() -> None:
    engine = PermissionEngine((_rule(permissions=("a", "b"), roles=(), require_all=False),))
    ctx = _ctx()
    assert engine.check(("a",), ctx, require_all=False) is True
    assert engine.check(("b",), ctx, require_all=False) is True
    assert engine.check(("c",), ctx, require_all=False) is False


def test_require_all_true_needs_all_permissions() -> None:
    engine = PermissionEngine((_rule(permissions=("a", "b"), roles=()),))
    ctx = _ctx()
    assert engine.check(("a", "b"), ctx, require_all=True) is True
    assert engine.check(("a", "b", "c"), ctx, require_all=True) is False


# ---------------------------------------------------------------------------
# Deny rules
# ---------------------------------------------------------------------------

def test_explicit_deny_overrides_allow() -> None:
    deny = PermissionRule(permissions=("cmd.run",), roles=("admin",), allow=False)
    allow = _rule(permissions=("cmd.run",), roles=("admin",), allow=True)
    # deny is evaluated first (first match wins on deny)
    engine = PermissionEngine((deny, allow))
    assert engine.check(("cmd.run",), _ctx(roles=("admin",))) is False


# ---------------------------------------------------------------------------
# Role matching in rules
# ---------------------------------------------------------------------------

def test_group_roles_are_included_in_all_roles() -> None:
    engine = PermissionEngine((_rule(permissions=("cmd.run",), roles=("group_admin",)),))
    ctx = _ctx(group_roles=("group_admin",))
    assert engine.check(("cmd.run",), ctx) is True


def test_wrong_role_does_not_match_rule() -> None:
    engine = PermissionEngine((_rule(permissions=("cmd.run",), roles=("admin",)),))
    assert engine.check(("cmd.run",), _ctx(roles=("member",))) is False


# ---------------------------------------------------------------------------
# Scope / resource / platform filters
# ---------------------------------------------------------------------------

def test_rule_scope_filter_respected() -> None:
    rule = PermissionRule(permissions=("cmd.run",), scopes=("group",), allow=True)
    engine = PermissionEngine((rule,))
    assert engine.check(("cmd.run",), _ctx(scope="group")) is True
    assert engine.check(("cmd.run",), _ctx(scope="private")) is False


def test_rule_resource_kind_filter_respected() -> None:
    rule = PermissionRule(permissions=("x",), resource_kinds=("provider",), allow=True)
    engine = PermissionEngine((rule,))
    assert engine.check(("x",), _ctx(resource_kind="provider")) is True
    assert engine.check(("x",), _ctx(resource_kind="command")) is False


def test_rule_platform_filter_respected() -> None:
    rule = PermissionRule(permissions=("x",), platforms=("onebot_v11",), allow=True)
    engine = PermissionEngine((rule,))
    assert engine.check(("x",), _ctx(platform="onebot_v11")) is True
    assert engine.check(("x",), _ctx(platform="other")) is False


# ---------------------------------------------------------------------------
# add_rule and check shorthand
# ---------------------------------------------------------------------------

def test_add_rule_dynamically() -> None:
    engine = PermissionEngine()
    assert engine.check(("cmd.run",), _ctx()) is False
    engine.add_rule(_rule(permissions=("cmd.run",), roles=()))
    assert engine.check(("cmd.run",), _ctx()) is True


def test_evaluate_returns_decision_with_reason() -> None:
    engine = PermissionEngine((_rule(permissions=("cmd.run",), roles=()),))
    decision = engine.evaluate(("cmd.run",), _ctx())
    assert decision.allowed is True
    assert decision.reason != ""
