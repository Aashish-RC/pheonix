"""
Pheonix Ollama Local Runtime Adapter
Communicates with local Ollama daemon via native REST API (port 11434).
"""

import time
import uuid
import httpx
from typing import List
from .base import LocalRuntimeAdapter
from ..models import InferenceRequest, InferenceResponse


class OllamaRuntimeAdapter(LocalRuntimeAdapter):
    """Adapter for running local models via Ollama."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        """Checks if Ollama daemon is active and listening."""
        try:
            with httpx.Client(timeout=1.5) as client:
                res = client.get(f"{self.base_url}/api/version")
                return res.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """Lists models downloaded into Ollama local storage."""
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    return [m.get("name") for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def chat_completion(self, request: InferenceRequest) -> InferenceResponse:
        """Dispatches chat request to Ollama /api/chat endpoint."""
        start_time = time.time()
        payload = {
            "model": request.model,
            "messages": request.messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens
            }
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(f"{self.base_url}/api/chat", json=payload)
                if res.status_code != 200:
                    raise RuntimeError(f"Ollama inference failed with status {res.status_code}: {res.text}")

                data = res.json()
                msg = data.get("message", {}).get("content", "")
                prompt_eval_count = data.get("prompt_eval_count", 0)
                eval_count = data.get("eval_count", 0)
                latency_ms = round((time.time() - start_time) * 1000, 2)

                return InferenceResponse(
                    id=f"ollama-{uuid.uuid4().hex[:8]}",
                    model=request.model,
                    runtime="ollama",
                    content=msg,
                    offline=True,
                    tokens_prompt=prompt_eval_count,
                    tokens_completion=eval_count,
                    latency_ms=latency_ms
                )
        except Exception as e:
            raise RuntimeError(f"Ollama execution error: {str(e)}") from e

    def stream_generate(self, model: str, prompt: str):
        """Streams raw token events from Ollama /api/generate endpoint."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
                    for line in response.iter_lines():
                        if line:
                            yield line
        except Exception as e:
            raise RuntimeError(f"Ollama streaming error: {str(e)}") from e

