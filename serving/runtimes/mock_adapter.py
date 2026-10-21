"""
Pheonix Mock Offline Runtime Adapter
Hermetic, network-isolated local runtime adapter for testing and CI validation.
"""

import time
import uuid
from typing import List
from .base import LocalRuntimeAdapter
from ..models import InferenceRequest, InferenceResponse


class MockOfflineRuntimeAdapter(LocalRuntimeAdapter):
    """
    Offline simulator adapter that executes completely without sockets or internet connectivity.
    Ensures deterministic, fast verification in automated CI test environments.
    """

    def __init__(self, available_models: List[str] = None):
        self._available_models = available_models or ["llama3.2:1b", "llama3.2:3b", "phi3:mini", "qwen2.5:3b"]
        self.is_online = True

    @property
    def name(self) -> str:
        return "mock-offline"

    def is_available(self) -> bool:
        return self.is_online

    def list_models(self) -> List[str]:
        return list(self._available_models)

    def chat_completion(self, request: InferenceRequest) -> InferenceResponse:
        """Executes simulated offline inference with realistic tokens and response."""
        start_time = time.time()
        
        last_msg = ""
        total_prompt_chars = 0
        for m in request.messages:
            content = m.get("content", "")
            if isinstance(content, str):
                total_prompt_chars += len(content)
                last_msg = content
            elif isinstance(content, list):
                total_prompt_chars += 50

        prompt_tokens = max(1, total_prompt_chars // 4)

        # Deterministic offline response simulation
        response_text = f"[Offline Local Inference via {self.name}] Generated answer for: '{last_msg[:48]}...'"
        completion_tokens = max(1, len(response_text) // 4)
        latency_ms = round((time.time() - start_time) * 1000 + 1.2, 2)

        return InferenceResponse(
            id=f"offline-{uuid.uuid4().hex[:8]}",
            model=request.model,
            runtime=self.name,
            content=response_text,
            offline=True,
            tokens_prompt=prompt_tokens,
            tokens_completion=completion_tokens,
            latency_ms=latency_ms
        )

    def stream_generate(self, model: str, prompt: str):
        """Simulates streamed token generation."""
        import json
        tokens = ["Pheonix", " local", " serving", " offline", " response", " for: ", prompt[:24]]
        for tok in tokens:
            yield json.dumps({"model": model, "response": tok, "done": False})
        yield json.dumps({"model": model, "response": "", "done": True})

