"""
Pheonix Serving Client SDK
High-level client for applications and agents to execute offline local inference.
"""

from typing import List, Dict, Any, Optional
from .models import DeviceProfile, ModelArtifact, InferenceRequest, InferenceResponse
from .core.engine import ModelServingEngine


class ServingClient:
    """
    Client for interacting with Pheonix Model Serving.
    """

    def __init__(self, engine: Optional[ModelServingEngine] = None):
        self.engine = engine or ModelServingEngine()

    @property
    def device_profile(self) -> DeviceProfile:
        return self.engine.profile

    def list_models(self) -> List[ModelArtifact]:
        """Lists available local model artifacts."""
        return self.engine.list_models()

    def list_active_runtimes(self) -> List[str]:
        """Lists currently active runtime daemons."""
        return self.engine.list_active_runtimes()

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        runtime: Optional[str] = None
    ) -> InferenceResponse:
        """Sends a structured chat request to the local serving engine."""
        request = InferenceRequest(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return self.engine.infer(request, runtime_name=runtime)

    def generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        runtime: Optional[str] = None
    ) -> str:
        """Convenience method to generate text from a single prompt string."""
        response = self.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            runtime=runtime
        )
        return response.content
