"""Background Agent Scheduler: Periodic background execution runner with visible log streaming."""

import threading
import time
from typing import Dict, List, Optional
from ..core.interfaces import BaseAgentScheduler, BaseInternalAgent, BaseVisibleLogStore
from ..core.models import (
    AgentLogEntry,
    AgentRunReport,
    AgentSeverity,
    AgentType,
)


class BackgroundAgentScheduler(BaseAgentScheduler):
    """Orchestrates periodic background agent execution cycles with thread-safe lifecycle control."""

    def __init__(self, visible_store: BaseVisibleLogStore):
        self.visible_store = visible_store
        self._agents: Dict[AgentType, BaseInternalAgent] = {}
        self._intervals: Dict[AgentType, float] = {}
        self._running = False
        self._stop_event = threading.Event()
        self._threads: List[threading.Thread] = []
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._running

    def register_agent(
        self, agent: BaseInternalAgent, interval_seconds: float = 60.0
    ) -> None:
        with self._lock:
            self._agents[agent.agent_type] = agent
            self._intervals[agent.agent_type] = interval_seconds

    def trigger_cycle(self, agent_type: AgentType) -> AgentRunReport:
        agent = self._agents.get(agent_type)
        if not agent:
            raise ValueError(f"Agent '{agent_type.value}' is not registered with the scheduler")
        return agent.run_cycle()

    def trigger_all(self) -> List[AgentRunReport]:
        reports = []
        for agent_type in list(self._agents.keys()):
            reports.append(self.trigger_cycle(agent_type))
        return reports

    def _agent_loop(self, agent: BaseInternalAgent, interval: float) -> None:
        while not self._stop_event.is_set():
            try:
                agent.run_cycle()
            except Exception as e:
                self.visible_store.append_log(
                    AgentLogEntry(
                        agent_type=agent.agent_type,
                        severity=AgentSeverity.ERROR,
                        action="agent_exception",
                        message=f"Agent '{agent.agent_type.value}' encountered error: {str(e)}",
                        metadata={"error": str(e)},
                    )
                )

            # Wait for interval or stop event
            self._stop_event.wait(timeout=interval)

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._threads.clear()

            for a_type, agent in self._agents.items():
                interval = self._intervals.get(a_type, 60.0)
                t = threading.Thread(
                    target=self._agent_loop,
                    args=(agent, interval),
                    name=f"InternalAgent-{a_type.value}",
                    daemon=True,
                )
                self._threads.append(t)
                t.start()

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._stop_event.set()
            for t in self._threads:
                t.join(timeout=1.0)
            self._threads.clear()
            self._running = False
