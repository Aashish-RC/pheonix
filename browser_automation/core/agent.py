"""Browser Use Automation Adapter and Security Interceptor Agent."""

import re
from typing import Callable, Dict, List, Optional
from ..agent.browser_agent import BrowserAgent
from ..core.interfaces import BaseBrowserSessionRunner, BaseConfirmationGate
from ..core.models import (
    ActionRiskLevel,
    BrowserAction,
    BrowserActionType,
    BrowserObservation,
    BrowserSessionProfile,
    BrowserTaskReport,
    ConfirmationStatus,
    utc_now,
)
from ..engine.confirmation_rules import ConfirmationRulesGate
from ..runtime.session_runner import BrowserSessionRunner

INTERCEPTOR_BUTTON_REGEX = re.compile(
    r"\b(submit|delete|pay|confirm|checkout|purchase|remove|cancel-subscription)\b",
    re.IGNORECASE,
)


class BrowserUseAdapter:
    """Adapter for browser-use and Playwright Chromium headless automation with security interceptor."""

    def __init__(
        self,
        headless: bool = True,
        interceptor_callback: Optional[Callable[[BrowserAction], bool]] = None,
    ):
        self.headless = headless
        self.interceptor_callback = interceptor_callback or self._default_security_interceptor
        self._browser = None
        self._page = None

    def _default_security_interceptor(self, action: BrowserAction) -> bool:
        """Default security interceptor: returns False (blocks/pauses) for consequential actions."""
        target = f"{action.target_selector or ''} {action.payload_text or ''}".lower()
        if action.action_type in (
            BrowserActionType.SUBMIT_FORM,
            BrowserActionType.PAYMENT_CHECKOUT,
            BrowserActionType.DELETE_DATA,
        ):
            return False

        if INTERCEPTOR_BUTTON_REGEX.search(target):
            return False

        return True


class BrowserUseAgent(BrowserAgent):
    """High-level Browser Use Agent with interactive page opening, text extraction, and form gating."""

    def __init__(
        self,
        session_runner: Optional[BaseBrowserSessionRunner] = None,
        confirmation_gate: Optional[BaseConfirmationGate] = None,
        adapter: Optional[BrowserUseAdapter] = None,
    ):
        super().__init__(
            session_runner=session_runner,
            confirmation_gate=confirmation_gate,
        )
        self.adapter = adapter or BrowserUseAdapter()

    def open_page(self, url: str) -> BrowserObservation:
        """Opens target URL in the headless browser profile and returns initial observation."""
        action = BrowserAction(action_type=BrowserActionType.NAVIGATE, url=url)
        return self.runner.execute_action(action)

    def extract_text(self) -> str:
        """Extracts text content from the current page."""
        obs = self.runner.get_current_observation()
        return obs.dom_snippet

    def step(
        self,
        action: BrowserAction,
        auto_approve: bool = False,
    ) -> BrowserTaskReport:
        """Executes a single browser step with confirmation pause on form submit or consequential buttons."""
        obs = self.runner.get_current_observation()

        # Check adapter security interceptor
        is_safe = self.adapter.interceptor_callback(action)
        allowed_by_gate = self.gate.evaluate_and_gate(action, current_url=obs.current_url)

        if not is_safe or not allowed_by_gate:
            if not auto_approve:
                return BrowserTaskReport(
                    task_id=action.action_id,
                    goal=f"Execute {action.action_type.value}",
                    actions_executed=0,
                    confirmations_requested=1,
                    confirmations_approved=0,
                    success=False,
                    final_url=obs.current_url,
                    error_message=(
                        f"Task paused: Consequential action '{action.action_type.value}' on target "
                        f"'{action.target_selector or action.url}' requires confirmation."
                    ),
                    action_log=[action],
                )
            else:
                self.gate.approve_action(action.action_id)

        # Execute safe or approved action
        self.runner.execute_action(action)
        final_obs = self.runner.get_current_observation()
        return BrowserTaskReport(
            task_id=action.action_id,
            goal=f"Execute {action.action_type.value}",
            actions_executed=1,
            confirmations_requested=0 if is_safe else 1,
            confirmations_approved=0 if is_safe else 1,
            success=True,
            final_url=final_obs.current_url,
            extracted_data={"title": final_obs.page_title, "snippet": final_obs.dom_snippet},
            action_log=[action],
        )


__all__ = [
    "BrowserAgent",
    "BrowserUseAgent",
    "BrowserUseAdapter",
    "INTERCEPTOR_BUTTON_REGEX",
]
