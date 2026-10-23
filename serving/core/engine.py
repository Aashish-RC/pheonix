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

    def _runtime_supports_model(self, adapter: LocalRuntimeAdapter, model: str) -> bool:
        available_models = adapter.list_models()
        return model in available_models or "default" in available_models

    def _select_runtime(
        self,
        model: str,
        runtime_name: Optional[str] = None,
    ) -> Optional[LocalRuntimeAdapter]:
        if runtime_name:
            adapter = self.get_runtime(runtime_name)
            if not adapter:
                raise ValueError(f"Runtime '{runtime_name}' is not registered.")
            if not adapter.is_available():
                raise RuntimeError(f"Runtime '{runtime_name}' is not currently available/reachable.")
            if not self._runtime_supports_model(adapter, model):
                raise RuntimeError(f"Runtime '{runtime_name}' does not provide model '{model}'.")
            return adapter

        for candidate_name in ["ollama", "llama.cpp", "mock-offline"]:
            adapter = self._runtimes.get(candidate_name)
            if adapter and adapter.is_available() and self._runtime_supports_model(adapter, model):
                return adapter
        return None

    def infer(self, request: InferenceRequest, runtime_name: Optional[str] = None) -> InferenceResponse:
        """
        Executes a local inference request under strict resource limits and hardware profiling.
        """
        # 1. Lookup model artifact requirements
        artifact = self.store.get_artifact(request.model)
        min_ram = artifact.min_ram_gb if artifact else 2.0
        min_vram = artifact.min_vram_gb if artifact else 0.0

        # 2. Enforce resource limits before runtime selection and inference.
        with self.resource_limiter.acquire_slot(required_ram_gb=min_ram, required_vram_gb=min_vram):
            selected_runtime = self._select_runtime(request.model, runtime_name)
            if not selected_runtime:
                raise RuntimeError(f"No available local runtime provides model '{request.model}'.")
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

        selected_runtime = self._select_runtime(model, runtime_name)

        if not selected_runtime:
            raise RuntimeError(f"No available local runtime provides model '{model}'.")

        # Stream generator
        return selected_runtime.stream_generate(model=model, prompt=prompt)
