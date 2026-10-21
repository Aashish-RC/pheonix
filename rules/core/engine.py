"""
Pheonix Central Rules Engine
Coordinates rule definitions, persistence, dynamic evaluation, and real-time event propagation.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

from ..models import (
    RuleDefinition,
    RuleScope,
    RuleEvaluationResult,
    RuleChangeEvent,
)
from .schema import evaluate_rules
from .dispatcher import RuleDispatcher
from .store import RulesStore


class RulesEngine:
    """
    Central authority for rule management and policy enforcement across Pheonix.
    Guarantees: A rule change reaches every app.
    """

    def __init__(self, store_path: Optional[Path] = None):
        self._rules: Dict[str, RuleDefinition] = {}
        self.dispatcher = RuleDispatcher()
        self.store = RulesStore(store_path) if store_path else None

        if self.store and self.store.exists():
            for r in self.store.load():
                self._rules[r.rule_id] = r

    def add_rule(self, rule: RuleDefinition) -> RuleDefinition:
        """Register a new rule and broadcast CREATED event to all connected apps."""
        self._rules[rule.rule_id] = rule
        if self.store:
            self.store.save(list(self._rules.values()))

        event = RuleChangeEvent(event_type="CREATED", rule=rule)
        self.dispatcher.broadcast(event)
        return rule

    def update_rule(self, rule: RuleDefinition) -> RuleDefinition:
        """Update an existing rule and broadcast UPDATED event to all connected apps."""
        existing = self._rules.get(rule.rule_id)
        rule.version = (existing.version + 1) if existing else 1
        rule.updated_at = time.time()

        self._rules[rule.rule_id] = rule
        if self.store:
            self.store.save(list(self._rules.values()))

        event = RuleChangeEvent(event_type="UPDATED", rule=rule)
        self.dispatcher.broadcast(event)
        return rule

    def toggle_rule(self, rule_id: str, enabled: bool) -> Optional[RuleDefinition]:
        """Enable or disable a rule and broadcast update."""
        rule = self._rules.get(rule_id)
        if not rule:
            return None

        rule.enabled = enabled
        rule.version += 1
        rule.updated_at = time.time()

        if self.store:
            self.store.save(list(self._rules.values()))

        event = RuleChangeEvent(event_type="TOGGLED", rule=rule)
        self.dispatcher.broadcast(event)
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """Remove a rule and broadcast DELETED event."""
        rule = self._rules.pop(rule_id, None)
        if not rule:
            return False

        if self.store:
            self.store.save(list(self._rules.values()))

        event = RuleChangeEvent(event_type="DELETED", rule=rule)
        self.dispatcher.broadcast(event)
        return True

    def get_rule(self, rule_id: str) -> Optional[RuleDefinition]:
        return self._rules.get(rule_id)

    def list_rules(
        self,
        scope: Optional[RuleScope] = None,
        enabled_only: bool = True,
    ) -> List[RuleDefinition]:
        """List rules filtered by scope or enablement."""
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        if scope is not None:
            rules = [r for r in rules if r.scope == RuleScope.GLOBAL or r.scope == scope]
        return sorted(rules, key=lambda r: r.priority)

    def evaluate(
        self,
        scope: RuleScope,
        context: Dict[str, Any],
    ) -> RuleEvaluationResult:
        """Evaluate context against rules for the target scope."""
        return evaluate_rules(list(self._rules.values()), scope, context)

    def subscribe(
        self,
        subscriber_id: str,
        callback: Callable[[RuleChangeEvent], None],
        scope_filter: Optional[RuleScope] = None,
    ):
        """Register application subscriber to receive instantaneous rule changes."""
        self.dispatcher.subscribe(subscriber_id, callback, scope_filter)

    def unsubscribe(self, subscriber_id: str):
        self.dispatcher.unsubscribe(subscriber_id)
