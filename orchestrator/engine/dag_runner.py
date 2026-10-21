"""Parallel DAG Runner: Executes task layers concurrently with fan-in barriers and cancellation."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import Any, Callable, Dict, List, Optional
from ..core.interfaces import BaseDAGRunner
from ..core.models import (
    PlanDAG,
    PlanExecutionReport,
    PlanNode,
    StepResult,
    TaskStatus,
)
from ..guard.budget_guard import BudgetGuard
from ..planner.multi_step_planner import MultiStepPlanner
from ..storage.sqlite_plan_store import SQLitePlanStore
from .cancellation import CancellationToken


class ParallelDAGRunner(BaseDAGRunner):
    """Executes PlanDAGs using parallel thread pools, respecting dependency barriers and cancellation."""

    def __init__(
        self,
        planner: Optional[MultiStepPlanner] = None,
        store: Optional[SQLitePlanStore] = None,
        budget_guard: Optional[BudgetGuard] = None,
    ):
        self.planner = planner or MultiStepPlanner()
        self.store = store or SQLitePlanStore(db_path=":memory:")
        self.budget_guard = budget_guard or BudgetGuard()
        self._handlers: Dict[str, Callable[[PlanNode, Dict[str, Any]], Any]] = {}

    def register_handler(self, action: str, handler: Callable[[PlanNode, Dict[str, Any]], Any]) -> None:
        """Register custom execution logic for an action type."""
        self._handlers[action] = handler

    def _execute_node(
        self,
        node: PlanNode,
        context: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> StepResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return StepResult(node_id=node.id, status=TaskStatus.CANCELLED, error=cancellation_token.reason)

        start_time = time.perf_counter()
        node.status = TaskStatus.RUNNING

        try:
            handler = self._handlers.get(node.action)
            if handler:
                output = handler(node, context)
            else:
                # Default executor
                time.sleep(0.01)  # Minimal simulated work
                output = f"Completed: {node.title}"

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            node.output = output
            node.status = TaskStatus.COMPLETED
            node.duration_ms = duration_ms

            return StepResult(
                node_id=node.id,
                status=TaskStatus.COMPLETED,
                output=output,
                duration_ms=round(duration_ms, 2),
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            node.error = str(e)
            node.status = TaskStatus.FAILED
            node.duration_ms = duration_ms

            return StepResult(
                node_id=node.id,
                status=TaskStatus.FAILED,
                error=str(e),
                duration_ms=round(duration_ms, 2),
            )

    def run_plan(
        self,
        plan: PlanDAG,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> PlanExecutionReport:
        start_plan_time = time.perf_counter()

        # Validate budget before running
        if not self.budget_guard.validate_plan_budget(plan):
            plan.status = TaskStatus.FAILED
            return PlanExecutionReport(
                plan_id=plan.id,
                status=TaskStatus.FAILED,
                total_nodes=len(plan.nodes),
                node_results={
                    nid: StepResult(node_id=nid, status=TaskStatus.FAILED, error="Budget exceeded limit")
                    for nid in plan.nodes
                },
            )

        layers = self.planner.get_execution_layers(plan)
        plan.status = TaskStatus.RUNNING
        self.store.save_plan(plan)

        context: Dict[str, Any] = {}
        node_results: Dict[str, StepResult] = {}
        plan_aborted = False

        max_workers = min(plan.max_concurrency, 16)

        for layer in layers:
            # Check for cancellation before starting the layer
            if cancellation_token and cancellation_token.is_cancelled:
                plan_aborted = True
                for nid in layer:
                    node = plan.nodes[nid]
                    node.status = TaskStatus.CANCELLED
                    node_results[nid] = StepResult(node_id=nid, status=TaskStatus.CANCELLED, error=cancellation_token.reason)
                    self.store.update_node(plan.id, nid, TaskStatus.CANCELLED, error=cancellation_token.reason)
                break

            # Parallel Fan-Out for independent nodes in this layer
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_node = {
                    executor.submit(
                        self._execute_node,
                        plan.nodes[nid],
                        context,
                        cancellation_token,
                    ): nid
                    for nid in layer
                }

                # Fan-In Join Barrier: wait for layer to finish
                for future in as_completed(future_to_node):
                    nid = future_to_node[future]
                    res = future.result()
                    node_results[nid] = res
                    context[nid] = res.output

                    # Persist node outcome
                    self.store.update_node(
                        plan_id=plan.id,
                        node_id=nid,
                        status=res.status,
                        output=res.output,
                        error=res.error,
                        duration_ms=res.duration_ms,
                    )

                    # Record cost
                    node = plan.nodes[nid]
                    self.budget_guard.record_step_cost(plan.id, node.cost_estimate)

                    if res.status == TaskStatus.FAILED:
                        plan_aborted = True
                    elif res.status == TaskStatus.CANCELLED:
                        plan_aborted = True

            if plan_aborted:
                # Mark remaining layers as SKIPPED or CANCELLED
                remaining_layers = layers[layers.index(layer) + 1 :]
                for rem_layer in remaining_layers:
                    for rem_nid in rem_layer:
                        status = TaskStatus.CANCELLED if (cancellation_token and cancellation_token.is_cancelled) else TaskStatus.SKIPPED
                        plan.nodes[rem_nid].status = status
                        node_results[rem_nid] = StepResult(node_id=rem_nid, status=status)
                        self.store.update_node(plan.id, rem_nid, status)
                break

        # Compute summary
        total_duration = (time.perf_counter() - start_plan_time) * 1000.0
        completed = sum(1 for r in node_results.values() if r.status == TaskStatus.COMPLETED)
        failed = sum(1 for r in node_results.values() if r.status == TaskStatus.FAILED)
        cancelled = sum(1 for r in node_results.values() if r.status == TaskStatus.CANCELLED)

        if cancelled > 0:
            final_status = TaskStatus.CANCELLED
        elif failed > 0:
            final_status = TaskStatus.FAILED
        else:
            final_status = TaskStatus.COMPLETED

        plan.status = final_status
        self.store.save_plan(plan)

        return PlanExecutionReport(
            plan_id=plan.id,
            status=final_status,
            total_nodes=len(plan.nodes),
            completed_nodes=completed,
            failed_nodes=failed,
            cancelled_nodes=cancelled,
            total_cost=self.budget_guard.get_cumulative_spend(plan.id),
            duration_ms=round(total_duration, 2),
            node_results=node_results,
        )
