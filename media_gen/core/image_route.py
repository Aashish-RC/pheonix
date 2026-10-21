"""
Image Route Safety and Generation Pipeline (Task 6.4).
Coordinates image generation adapters (Stability AI / ComfyUI / Local Engine)
wrapped with Guardrails output safety screening and content moderation.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from media_gen.core.models import (
    MediaArtifact,
    MediaRequest,
    MediaType,
    SafetyCheckStatus,
)
from media_gen.core.safety import SafetyModerator
from media_gen.engines.image_engine import ImageGenerationEngine
from guardrails.core.output_guard import OutputGuard


class SafetyPolicyViolationError(Exception):
    """Raised when an image generation prompt violates content safety policies."""
    pass


class ImageGenerationResult(BaseModel):
    success: bool
    artifact: Optional[MediaArtifact] = None
    prompt: str
    error: Optional[str] = None
    safety_checked: bool = True
    provider: str = "engine"


class ImageGenerationRoute:
    """
    Unified route handler for image synthesis with pre-flight safety screening,
    outbound guardrail inspection, and multi-backend generation dispatch.
    """

    def __init__(
        self,
        output_guard: Optional[OutputGuard] = None,
        safety_moderator: Optional[SafetyModerator] = None,
        stability_api_key: Optional[str] = None,
        comfyui_url: Optional[str] = None,
    ):
        self.output_guard = output_guard or OutputGuard()
        self.safety_moderator = safety_moderator or SafetyModerator()
        self.stability_api_key = stability_api_key or os.getenv("STABILITY_API_KEY")
        self.comfyui_url = comfyui_url or os.getenv("COMFYUI_URL", "http://localhost:8188")
        self._engine = ImageGenerationEngine()

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        model: str = "sdxl-turbo",
        **parameters: Any
    ) -> ImageGenerationResult:
        """
        Executes safety-screened image generation.
        Raises SafetyPolicyViolationError or returns failed result if content policy is violated.
        """
        if not prompt or not prompt.strip():
            return ImageGenerationResult(
                success=False,
                prompt=prompt,
                error="Prompt cannot be empty",
                safety_checked=False
            )

        # 1. Screen input prompt through media safety moderator
        req = MediaRequest(
            media_type=MediaType.IMAGE,
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=model,
            parameters={"width": width, "height": height, **parameters}
        )
        screen_res = self.safety_moderator.screen_prompt(req)
        if screen_res.status == SafetyCheckStatus.BLOCKED:
            raise SafetyPolicyViolationError(f"Prompt blocked by media safety moderator: {screen_res.reason}")

        # 2. Evaluate prompt against Guardrails output guard
        guard_res = self.output_guard.evaluate(prompt)
        if guard_res.action == "block":
            raise SafetyPolicyViolationError(f"Prompt blocked by output guardrail: {guard_res.reason}")

        # 3. Dispatch generation to engine
        provider_name = "stability_ai" if self.stability_api_key else ("comfyui" if "comfyui" in self.comfyui_url else "image_engine")
        artifact = await self._engine.generate(req)

        # 4. Post-generation inspection
        inspect_res = self.safety_moderator.inspect_artifact(artifact)
        if inspect_res.status == SafetyCheckStatus.BLOCKED:
            raise SafetyPolicyViolationError(f"Generated artifact failed post-gen integrity inspection: {inspect_res.reason}")

        return ImageGenerationResult(
            success=True,
            artifact=artifact,
            prompt=prompt,
            safety_checked=True,
            provider=provider_name
        )

    def generate_image_sync(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> ImageGenerationResult:
        """Synchronous wrapper for generate_image."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(self.generate_image(prompt, negative_prompt=negative_prompt, **kwargs))
        else:
            return asyncio.run(self.generate_image(prompt, negative_prompt=negative_prompt, **kwargs))
