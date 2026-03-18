from __future__ import annotations

from .models import AuthorizationContext, PermissionDecision, PermissionRule


class PermissionEngine:
    def __init__(self, rules: tuple[PermissionRule, ...] = ()) -> None:
        self._rules = list(rules)

    def add_rule(self, rule: PermissionRule) -> None:
        self._rules.append(rule)

    def evaluate(
        self,
        permissions: tuple[str, ...],
        context: AuthorizationContext,
        require_all: bool = True,
    ) -> PermissionDecision:
        if not permissions:
            return PermissionDecision(allowed=True, reason="no permissions requested")

        subject_roles = set(context.subject.all_roles)
        if "owner" in subject_roles or "super_admin" in subject_roles:
            return PermissionDecision(allowed=True, reason="bypassed by elevated role")

        matched_rules: list[PermissionRule] = []
        allowed_permissions: set[str] = set()

        for rule in self._rules:
            if not rule.matches_context(context):
                continue

            overlap = set(rule.permissions).intersection(permissions)
            if not overlap and rule.permissions:
                continue

            matched_rules.append(rule)
            if not rule.allow:
                return PermissionDecision(
                    allowed=False,
                    reason="explicit deny rule matched",
                    matched_rules=tuple(matched_rules),
                )

            if rule.permissions:
                allowed_permissions.update(overlap)

        requested = set(permissions)
        if require_all:
            allowed = requested.issubset(allowed_permissions)
        else:
            allowed = not requested.isdisjoint(allowed_permissions)

        reason = (
            "allowed by matching rules" if allowed else "missing required permissions"
        )
        return PermissionDecision(
            allowed=allowed,
            reason=reason,
            matched_rules=tuple(matched_rules),
        )

    def check(
        self,
        permissions: tuple[str, ...],
        context: AuthorizationContext,
        require_all: bool = True,
    ) -> bool:
        return self.evaluate(permissions, context, require_all=require_all).allowed
