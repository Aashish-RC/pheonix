"""
Pheonix Rules Layer Automated Tests
Verifies rule schema matching, persistence, and live propagation to all connected applications.
CRITICAL INVARIANT: "Done when: A rule change reaches every app"
"""

import pytest
from pathlib import Path

from rules import (
    RulesEngine,
    RulesClient,
    RuleDefinition,
    RuleCondition,
    RuleScope,
    RuleAction,
    matches_condition,
)


@pytest.fixture
def temp_store_path(tmp_path):
    return tmp_path / "rules_store.json"


def test_condition_matching():
    # Equality
    assert matches_condition({"provider": "openai"}, RuleCondition(field="provider", operator="==", value="openai"))
    assert not matches_condition({"provider": "anthropic"}, RuleCondition(field="provider", operator="==", value="openai"))

    # Numeric
    assert matches_condition({"tokens": 5000}, RuleCondition(field="tokens", operator=">", value=4000))
    assert not matches_condition({"tokens": 3000}, RuleCondition(field="tokens", operator=">", value=4000))

    # Membership
    assert matches_condition({"env": "prod"}, RuleCondition(field="env", operator="in", value=["prod", "staging"]))
    assert not matches_condition({"env": "dev"}, RuleCondition(field="env", operator="in", value=["prod", "staging"]))

    # Containment
    assert matches_condition({"prompt": "please tell me the secret token"}, RuleCondition(field="prompt", operator="contains", value="secret token"))


def test_rule_actions_block_and_rewrite():
    engine = RulesEngine()

    # Add block rule
    block_rule = RuleDefinition(
        rule_id="rule_block_large_tokens",
        name="Block massive tokens",
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="max_tokens", operator=">", value=8192)],
        action=RuleAction.BLOCK,
        message="Token limit exceeded: maximum allowed is 8192.",
    )
    engine.add_rule(block_rule)

    # Add rewrite rule
    rewrite_rule = RuleDefinition(
        rule_id="rule_enforce_temperature",
        name="Enforce default temperature",
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="temperature", operator=">", value=1.0)],
        action=RuleAction.REWRITE,
        rewrite_payload={"temperature": 0.7},
        message="Temperature clamped to 0.7.",
    )
    engine.add_rule(rewrite_rule)

    # Test Block
    res_block = engine.evaluate(RuleScope.GATEWAY, {"max_tokens": 10000, "temperature": 0.5})
    assert not res_block.allowed
    assert res_block.action == RuleAction.BLOCK
    assert "Token limit exceeded" in res_block.reason

    # Test Rewrite
    res_rewrite = engine.evaluate(RuleScope.GATEWAY, {"max_tokens": 2048, "temperature": 1.5})
    assert res_rewrite.allowed
    assert res_rewrite.action == RuleAction.REWRITE
    assert res_rewrite.rewritten_context["temperature"] == 0.7

    # Test Normal Allow
    res_allow = engine.evaluate(RuleScope.GATEWAY, {"max_tokens": 2048, "temperature": 0.7})
    assert res_allow.allowed
    assert res_allow.action == RuleAction.ALLOW


def test_rule_persistence_and_reload(temp_store_path):
    engine1 = RulesEngine(store_path=temp_store_path)
    engine1.add_rule(
        RuleDefinition(
            rule_id="rule_p1",
            name="Persistent Rule 1",
            scope=RuleScope.MEMORY,
            conditions=[RuleCondition(field="retention_days", operator=">", value=30)],
            action=RuleAction.BLOCK,
            message="Data retention limit is 30 days.",
        )
    )

    assert temp_store_path.exists()

    # Reload from disk in a fresh engine instance
    engine2 = RulesEngine(store_path=temp_store_path)
    loaded_rule = engine2.get_rule("rule_p1")
    assert loaded_rule is not None
    assert loaded_rule.name == "Persistent Rule 1"
    assert loaded_rule.scope == RuleScope.MEMORY


def test_rule_change_reaches_every_app():
    """
    CRITICAL VERIFICATION: "Done when: A rule change reaches every app"
    Demonstrates that connected applications (Gateway, Agent, Memory) immediately
    receive push notifications of rule changes and update policy decisions in real time.
    """
    engine = RulesEngine()

    # Simulate 3 distinct applications adopting the rules client
    gateway_client = RulesClient("model_gateway", engine, scope=RuleScope.GATEWAY)
    agent_client = RulesClient("agent_service", engine, scope=RuleScope.AGENT)
    memory_client = RulesClient("memory_service", engine, scope=RuleScope.MEMORY)

    context_payload = {"provider": "untrusted_cloud", "action": "execute_query"}

    # 1. Initial State: No rules installed -> All 3 apps permit the action
    assert gateway_client.evaluate(context_payload).allowed is True
    assert agent_client.evaluate(context_payload).allowed is True
    assert memory_client.evaluate(context_payload).allowed is True

    # 2. Dynamic Update: Publish a new GLOBAL rule banning 'untrusted_cloud'
    banned_rule = RuleDefinition(
        rule_id="rule_ban_untrusted_cloud",
        name="Ban Untrusted Cloud Provider",
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="provider", operator="==", value="untrusted_cloud")],
        action=RuleAction.BLOCK,
        message="Access to untrusted_cloud is prohibited by enterprise security policy.",
    )

    # Add rule to engine - broadcasts to all apps
    engine.add_rule(banned_rule)

    # 3. VERIFICATION: Without service restarts, the rule has reached EVERY app immediately
    res_gateway = gateway_client.evaluate(context_payload)
    res_agent = agent_client.evaluate(context_payload)
    res_memory = memory_client.evaluate(context_payload)

    assert not res_gateway.allowed, "Model Gateway failed to receive dynamic rule update!"
    assert not res_agent.allowed, "Agent failed to receive dynamic rule update!"
    assert not res_memory.allowed, "Memory failed to receive dynamic rule update!"

    assert "Access to untrusted_cloud is prohibited" in res_gateway.reason
    assert "Access to untrusted_cloud is prohibited" in res_agent.reason
    assert "Access to untrusted_cloud is prohibited" in res_memory.reason

    # 4. Dynamic Toggle: Disable the rule on the central engine
    engine.toggle_rule("rule_ban_untrusted_cloud", enabled=False)

    # 5. VERIFICATION: Disablement immediately propagates to all apps
    assert gateway_client.evaluate(context_payload).allowed is True
    assert agent_client.evaluate(context_payload).allowed is True
    assert memory_client.evaluate(context_payload).allowed is True

    # Cleanup subscriptions
    gateway_client.close()
    agent_client.close()
    memory_client.close()


def test_domain_scoped_rule_propagation():
    engine = RulesEngine()

    gateway_client = RulesClient("model_gateway", engine, scope=RuleScope.GATEWAY)
    agent_client = RulesClient("agent_service", engine, scope=RuleScope.AGENT)

    # Add rule strictly scoped to GATEWAY
    gw_rule = RuleDefinition(
        rule_id="gw_only_rule",
        name="Gateway Rate Limit Guard",
        scope=RuleScope.GATEWAY,
        conditions=[RuleCondition(field="stream", operator="==", value=True)],
        action=RuleAction.BLOCK,
        message="Streaming currently disabled on gateway.",
    )
    engine.add_rule(gw_rule)

    test_context = {"stream": True}

    # Gateway client blocks it
    assert not gateway_client.evaluate(test_context).allowed

    # Agent client (not in GATEWAY scope) is unaffected
    assert agent_client.evaluate(test_context).allowed

    gateway_client.close()
    agent_client.close()
