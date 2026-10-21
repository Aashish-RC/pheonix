"""Pheonix Recommender Service: Evaluates candidates, arbitrates, and delivers decisions with transparent reasoning."""

from typing import List, Optional
from ..core.interfaces import (
    BaseRecommenderService,
    BaseSecondOpinionArbiter,
    BaseTelemetryScorer,
)
from ..core.models import (
    CandidateScore,
    ModelCandidate,
    RecommendationDecision,
    TaskProfile,
    ToolCandidate,
)
from .second_opinion import SecondOpinionArbiter
from .telemetry_scorer import TelemetryScorer


class RecommenderService(BaseRecommenderService):
    """Orchestrates model and tool recommendations with second-opinion arbitration."""

    def __init__(
        self,
        scorer: Optional[BaseTelemetryScorer] = None,
        arbiter: Optional[BaseSecondOpinionArbiter] = None,
    ):
        self.scorer = scorer or TelemetryScorer()
        self.arbiter = arbiter or SecondOpinionArbiter()

    def recommend_model(
        self, task: TaskProfile, candidates: List[ModelCandidate]
    ) -> RecommendationDecision:
        if not candidates:
            raise ValueError("No model candidates provided for recommendation")

        # Score all candidates
        scores: List[CandidateScore] = [
            self.scorer.score_model(c, task) for c in candidates
        ]
        # Sort descending by composite score
        scores.sort(key=lambda s: s.composite_score, reverse=True)

        top_score = scores[0]
        runner_up = scores[1] if len(scores) > 1 else None

        confidence_margin = (
            top_score.composite_score - runner_up.composite_score
            if runner_up
            else 1.0
        )

        chosen_id = top_score.candidate_id
        second_opinion_triggered = False
        second_opinion_notes = None

        if self.arbiter.should_trigger_second_opinion(top_score, runner_up, task):
            second_opinion_triggered = True
            if runner_up:
                chosen_id, second_opinion_notes = self.arbiter.arbitrate(
                    top_score, runner_up, task
                )
            else:
                second_opinion_notes = (
                    "Single candidate available; verified acceptable baseline."
                )

        one_line_reason = (
            f"Auto selected '{chosen_id}' (composite: {top_score.composite_score:.3f}, "
            f"cost: ${top_score.estimated_cost_usd:.4f}, latency: {top_score.estimated_latency_ms:.0f}ms): "
            f"optimal fit for {task.task_type.value} under {task.goal.value} policy"
        )

        return RecommendationDecision(
            task_id=task.task_id,
            recommended_id=chosen_id,
            candidate_type="model",
            composite_score=top_score.composite_score,
            runner_up_id=runner_up.candidate_id if runner_up else None,
            runner_up_score=runner_up.composite_score if runner_up else None,
            confidence_margin=round(confidence_margin, 4),
            one_line_reason=one_line_reason,
            second_opinion_triggered=second_opinion_triggered,
            second_opinion_notes=second_opinion_notes,
        )

    def recommend_tool(
        self, task: TaskProfile, candidates: List[ToolCandidate]
    ) -> RecommendationDecision:
        if not candidates:
            raise ValueError("No tool candidates provided for recommendation")

        scores: List[CandidateScore] = [
            self.scorer.score_tool(c, task) for c in candidates
        ]
        scores.sort(key=lambda s: s.composite_score, reverse=True)

        top_score = scores[0]
        runner_up = scores[1] if len(scores) > 1 else None

        confidence_margin = (
            top_score.composite_score - runner_up.composite_score
            if runner_up
            else 1.0
        )

        chosen_id = top_score.candidate_id
        second_opinion_triggered = False
        second_opinion_notes = None

        if self.arbiter.should_trigger_second_opinion(top_score, runner_up, task):
            second_opinion_triggered = True
            if runner_up:
                chosen_id, second_opinion_notes = self.arbiter.arbitrate(
                    top_score, runner_up, task
                )
            else:
                second_opinion_notes = (
                    "Single tool available; verified acceptable baseline."
                )

        one_line_reason = (
            f"Auto selected tool '{chosen_id}' (composite: {top_score.composite_score:.3f}, "
            f"overhead: ${top_score.estimated_cost_usd:.4f}): matched {task.task_type.value} requirements"
        )

        return RecommendationDecision(
            task_id=task.task_id,
            recommended_id=chosen_id,
            candidate_type="tool",
            composite_score=top_score.composite_score,
            runner_up_id=runner_up.candidate_id if runner_up else None,
            runner_up_score=runner_up.composite_score if runner_up else None,
            confidence_margin=round(confidence_margin, 4),
            one_line_reason=one_line_reason,
            second_opinion_triggered=second_opinion_triggered,
            second_opinion_notes=second_opinion_notes,
        )
