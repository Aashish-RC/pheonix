"""
Pheonix Model Serving Engine
Coordinates hardware profiling, memory resource safety, model artifacts, and local runtime adapters.
"""

from typing import Dict, List, Optional
from ..models import (
    DeviceProfile,
    ResourceLimits,
    ModelArtifact,
    InferenceRequest,
    InferenceResponse
)
from .device_profiler import DeviceProfiler
from .resource_limiter import ResourceLimiter, ResourceLimitExceededError, ConcurrencyLimitExceededError
from .model_store import ModelStore
from ..runtimes.base import LocalRuntimeAdapter
from ..runtimes.ollama_adapter import OllamaRuntimeAdapter
from ..runtimes.llamacpp_adapter import LlamaCppRuntimeAdapter
from ..runtimes.mock_adapter import MockOfflineRuntimeAdapter


class ModelServingEngine:
    """
    Central coordinator for local offline model serving in Pheonix.
    """

    def __init__(
        self,
        profile: Optional[DeviceProfile] = None,
        limits: Optional[ResourceLimits] = None,
        store: Optional[ModelStore] = None
    ):
        self.profile = profile or DeviceProfiler.profile()
        self.limits = limits or ResourceLimits()
        self.resource_limiter = ResourceLimiter(self.limits)
        self.store = store or ModelStore()
        self._runtimes: Dict[str, LocalRuntimeAdapter] = {}

        # Register standard default runtimes
        self.register_runtime(OllamaRuntimeAdapter())
        self.register_runtime(LlamaCppRuntimeAdapter())
        self.register_runtime(MockOfflineRuntimeAdapter())

    def register_runtime(self, adapter: LocalRuntimeAdapter) -> None:
        """Registers a runtime adapter into the serving engine."""
        self._runtimes[adapter.name.lower()] = adapter

    def get_runtime(self, name: str) -> Optional[LocalRuntimeAdapter]:
        """Retrieves a runtime adapter by name."""
        return self._runtimes.get(name.lower())

    def list_active_runtimes(self) -> List[str]:
        """Returns names of all currently available/reachable local runtime adapters."""
        return [name for name, r in self._runtimes.items() if r.is_available()]

    def list_models(self) -> List[ModelArtifact]:
        """Lists all model artifacts registered in the store."""
        return self.store.list_artifacts()

    def infer(self, request: InferenceRequest, runtime_name: Optional[str] = None) -> InferenceResponse:
        """
        Executes a local inference request under strict resource limits and hardware profiling.
        """
        # 1. Lookup model artifact requirements
        artifact = self.store.get_artifact(request.model)
        min_ram = artifact.min_ram_gb if artifact else 2.0
        min_vram = artifact.min_vram_gb if artifact else 0.0

        # 2. Select appropriate runtime
        selected_runtime: Optional[LocalRuntimeAdapter] = None
        if runtime_name:
            adapter = self.get_runtime(runtime_name)
            if not adapter:
                raise ValueError(f"Runtime '{runtime_name}' is not registered.")
            if not adapter.is_available():
                raise RuntimeError(f"Runtime '{runtime_name}' is not currently available/reachable.")
            selected_runtime = adapter
        else:
            # Auto-select first available runtime: prioritize live daemon (ollama/llama.cpp), fallback to offline
            for candidate_name in ["ollama", "llama.cpp", "mock-offline"]:
                adapter = self._runtimes.get(candidate_name)
                if adapter and adapter.is_available():
                    selected_runtime = adapter
                    break

        if not selected_runtime:
            raise RuntimeError("No local model serving runtime is currently available.")

        # 3. Enforce resource limits (RAM safety threshold and concurrency cap)
        with self.resource_limiter.acquire_slot(required_ram_gb=min_ram, required_vram_gb=min_vram):
            response = selected_runtime.chat_completion(request)

        # Task 1.2: Telemetry emission for serving inference
        try:
            from observability.core.tracer import TelemetryCollector
            TelemetryCollector.get_instance().emit(
                module="serving",
                operation="llm_inference",
                duration_ms=response.latency_ms,
                status_code=200,
                token_usage={
                    "prompt_tokens": response.tokens_prompt,
                    "completion_tokens": response.tokens_completion,
                    "total_tokens": response.tokens_prompt + response.tokens_completion,
                },
                metadata={"model": response.model, "runtime": response.runtime, "offline": response.offline},
            )
        except Exception:
            pass

        return response

    def stream_generate(self, model: str, prompt: str, runtime_name: Optional[str] = None):
        """
        Executes streamed token generation with device-profile validation.
        Validates that device memory capacity supports the model artifact.
        """
        artifact = self.store.get_artifact(model)
        min_ram = artifact.min_ram_gb if artifact else 2.0
        min_vram = artifact.min_vram_gb if artifact else 0.0

        # Device profile validation: model cannot exceed total device RAM
        if min_ram > self.profile.total_ram_gb:
            raise ResourceLimitExceededError(
                f"Device profile insufficient: Model '{model}' requires {min_ram}GB RAM, but device has only {self.profile.total_ram_gb:.1f}GB."
            )

        # Select runtime adapter
        selected_runtime: Optional[LocalRuntimeAdapter] = None
        if runtime_name:
            selected_runtime = self.get_runtime(runtime_name)
        else:
            for candidate in ["ollama", "llama.cpp", "mock-offline"]:
                adapter = self._runtimes.get(candidate)
                if adapter and adapter.is_available():
                    selected_runtime = adapter
                    break

        if not selected_runtime:
            raise RuntimeError("No local runtime available for streaming generation.")

        # Stream generator
        return selected_runtime.stream_generate(model=model, prompt=prompt)

