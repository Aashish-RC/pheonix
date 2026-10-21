"""
Pheonix llama.cpp Local Runtime Adapter
Communicates with llama.cpp server via OpenAI-compatible endpoints (port 8080).
"""

import time
import uuid
import httpx
from typing import List
from .base import LocalRuntimeAdapter
from ..models import InferenceRequest, InferenceResponse


class LlamaCppRuntimeAdapter(LocalRuntimeAdapter):
    """Adapter for running local models via llama.cpp server."""

    def __init__(self, base_url: str = "http://127.0.0.1:8080", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "llama.cpp"

    def is_available(self) -> bool:
        """Checks if llama.cpp server is reachable via /health."""
        try:
            with httpx.Client(timeout=1.5) as client:
                res = client.get(f"{self.base_url}/health")
                return res.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """Lists available models from llama.cpp /v1/models."""
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.base_url}/v1/models")
                if res.status_code == 200:
                    data = res.json()
                    return [m.get("id") for m in data.get("data", [])]
        except Exception:
            pass
        return ["default"]

    def chat_completion(self, request: InferenceRequest) -> InferenceResponse:
        """Dispatches chat request to llama.cpp /v1/chat/completions."""
        start_time = time.time()
        payload = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(f"{self.base_url}/v1/chat/completions", json=payload)
                if res.status_code != 200:
                    raise RuntimeError(f"llama.cpp inference failed with status {res.status_code}: {res.text}")

                data = res.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                latency_ms = round((time.time() - start_time) * 1000, 2)

                return InferenceResponse(
                    id=data.get("id", f"llamacpp-{uuid.uuid4().hex[:8]}"),
                    model=request.model,
                    runtime="llama.cpp",
                    content=content,
                    offline=True,
                    tokens_prompt=usage.get("prompt_tokens", 0),
                    tokens_completion=usage.get("completion_tokens", 0),
                    latency_ms=latency_ms
                )
        except Exception as e:
            raise RuntimeError(f"llama.cpp execution error: {str(e)}") from e
