"""
Pheonix Model Serving Test Suite
Validates device hardware profiling, resource limits, offline inference, and runtime adapters.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from serving.models import (
    DeviceProfile,
    ResourceLimits,
    ModelArtifact,
    InferenceRequest,
    InferenceResponse
)
from serving.core.device_profiler import DeviceProfiler
from serving.core.resource_limiter import (
    ResourceLimiter,
    ResourceLimitExceededError,
    ConcurrencyLimitExceededError
)
from serving.core.model_store import ModelStore
from serving.core.engine import ModelServingEngine
from serving.runtimes.mock_adapter import MockOfflineRuntimeAdapter
from serving.runtimes.ollama_adapter import OllamaRuntimeAdapter
from serving.runtimes.llamacpp_adapter import LlamaCppRuntimeAdapter
from serving.client import ServingClient


class TestDeviceProfiler:
    """Tests hardware device discovery and compute capability profiling."""

    def test_profile_returns_valid_system_spec(self):
        profile = DeviceProfiler.profile()
        assert profile.physical_cores >= 1
        assert profile.logical_cores >= 1
        assert profile.total_ram_gb > 0.5
        assert profile.available_ram_gb > 0.0
        assert profile.acceleration in ["cpu", "cuda", "metal", "rocm", "directml"]
        assert profile.max_recommended_parameters_billion >= 1.0

    def test_calculate_max_params_thresholds(self):
        # 32B models require >= 24GB
        assert DeviceProfiler._calculate_max_params(32.0, 24.0, "cuda") == 32.0
        # 14B models require >= 12GB
        assert DeviceProfiler._calculate_max_params(16.0, 12.0, "cuda") == 14.0
        # 8B models require >= 6.5GB
        assert DeviceProfiler._calculate_max_params(8.0, 8.0, "cuda") == 8.0
        # 3B models require >= 3.5GB
        assert DeviceProfiler._calculate_max_params(4.0, 0.0, "cpu") == 3.0
        # Low RAM fallback
        assert DeviceProfiler._calculate_max_params(2.0, 0.0, "cpu") == 1.5


class TestResourceLimiter:
    """Tests host memory protection and concurrency bounds."""

    def test_acquires_and_releases_slot_cleanly(self):
        limiter = ResourceLimiter(ResourceLimits(max_concurrent_streams=2, enforce_ram_limits=False))
        assert limiter.active_streams == 0

        with limiter.acquire_slot():
            assert limiter.active_streams == 1
            with limiter.acquire_slot():
                assert limiter.active_streams == 2

        assert limiter.active_streams == 0

    def test_blocks_concurrency_exceeded(self):
        limiter = ResourceLimiter(ResourceLimits(max_concurrent_streams=1, enforce_ram_limits=False))

        with limiter.acquire_slot():
            with pytest.raises(ConcurrencyLimitExceededError) as exc_info:
                with limiter.acquire_slot():
                    pass
            assert "Maximum concurrent local streams (1) reached" in str(exc_info.value)

        # Slot released despite error
        assert limiter.active_streams == 0

    def test_enforces_ram_safety_threshold(self):
        # Setting threshold to impossible 1% triggers ResourceLimitExceededError
        strict_limits = ResourceLimits(max_ram_usage_percent=10.0)
        limiter = ResourceLimiter(strict_limits)

        with pytest.raises(ResourceLimitExceededError) as exc_info:
            limiter.check_limits()
        assert "exceeding safety threshold" in str(exc_info.value)


class TestModelStore:
    """Tests local quantized model catalog and artifact management."""

    def test_default_catalog_contains_popular_quantized_models(self, tmp_path):
        store = ModelStore(store_dir=tmp_path)
        artifacts = store.list_artifacts()
        ids = [a.model_id for a in artifacts]

        assert "llama3.2:1b" in ids
        assert "llama3.2:3b" in ids
        assert "phi3:mini" in ids
        assert "mistral:7b-instruct" in ids

    def test_registers_and_retrieves_custom_artifact(self, tmp_path):
        store = ModelStore(store_dir=tmp_path)
        custom_art = ModelArtifact(
            model_id="deepseek-r1:1.5b",
            parameter_size="1.5B",
            format="GGUF",
            quantization="Q4_K_M",
            file_size_bytes=1_100_000_000,
            min_ram_gb=2.0,
            min_vram_gb=1.5,
            context_length=16384
        )
        store.register_artifact(custom_art)

        retrieved = store.get_artifact("deepseek-r1:1.5b")
        assert retrieved is not None
        assert retrieved.parameter_size == "1.5B"
        assert retrieved.context_length == 16384


class TestOfflineInference:
    """Verification Gate: 'Done when: A local model answers offline'."""

    def test_mock_offline_runtime_answers_without_network(self):
        adapter = MockOfflineRuntimeAdapter()
        assert adapter.is_available() is True
        assert len(adapter.list_models()) > 0

        req = InferenceRequest(
            model="llama3.2:3b",
            messages=[{"role": "user", "content": "Explain quantum computing in one sentence."}],
            temperature=0.7,
            max_tokens=128
        )
        res = adapter.chat_completion(req)

        assert res.offline is True
        assert res.runtime == "mock-offline"
        assert len(res.content) > 10
        assert res.tokens_prompt > 0
        assert res.tokens_completion > 0
        assert res.latency_ms > 0

    def test_model_serving_engine_executes_offline_inference(self):
        engine = ModelServingEngine(limits=ResourceLimits(enforce_ram_limits=False))
        req = InferenceRequest(
            model="llama3.2:1b",
            messages=[{"role": "user", "content": "What is the capital of France?"}]
        )
        res = engine.infer(req)

        assert res.offline is True
        assert res.model == "llama3.2:1b"
        assert len(res.content) > 0

    def test_serving_client_sdk_convenience_methods(self):
        engine = ModelServingEngine(limits=ResourceLimits(enforce_ram_limits=False))
        client = ServingClient(engine=engine)
        # Verify device profile property
        profile = client.device_profile
        assert profile.total_ram_gb > 0

        # Verify generate method
        answer = client.generate(
            model="llama3.2:1b",
            prompt="Hello from Pheonix offline agent!"
        )
        assert isinstance(answer, str)
        assert len(answer) > 0

    def test_ram_limit_blocks_when_insufficient_ram(self):
        # Setting a required RAM higher than available memory raises ResourceLimitExceededError
        engine = ModelServingEngine(limits=ResourceLimits(enforce_ram_limits=True, max_ram_usage_percent=99.9))
        custom_art = ModelArtifact(
            model_id="huge-model:70b",
            parameter_size="70B",
            min_ram_gb=1000.0  # Impossible 1000GB RAM
        )
        engine.store.register_artifact(custom_art)

        req = InferenceRequest(
            model="huge-model:70b",
            messages=[{"role": "user", "content": "test"}]
        )
        with pytest.raises(ResourceLimitExceededError) as exc_info:
            engine.infer(req)
        assert "Insufficient RAM available" in str(exc_info.value)

    def test_runtime_probe_handles_unreachable_daemons_gracefully(self):
        # Point to non-existent ports
        dead_ollama = OllamaRuntimeAdapter(base_url="http://127.0.0.1:59999")
        assert dead_ollama.is_available() is False
        assert dead_ollama.list_models() == []

        dead_llamacpp = LlamaCppRuntimeAdapter(base_url="http://127.0.0.1:59998")
        assert dead_llamacpp.is_available() is False

    def test_serving_generate_streaming_endpoint(self):
        """
        Validates Task O2: expose /generate endpoint that proxies with device-profile checks.
        """
        from fastapi.testclient import TestClient
        from serving.server import create_serving_app

        engine = ModelServingEngine()
        app = create_serving_app(engine)
        client = TestClient(app)

        # Health endpoint
        h_res = client.get("/health")
        assert h_res.status_code == 200
        assert h_res.json()["status"] == "healthy"

        # Generate streaming endpoint with llama3.2
        gen_res = client.post(
            "/generate",
            json={"model": "llama3.2:1b", "prompt": "Explain quantum computing briefly.", "stream": True},
        )
        assert gen_res.status_code == 200
        assert "text/event-stream" in gen_res.headers["content-type"]
        assert len(gen_res.text) > 0
        assert "llama3.2:1b" in gen_res.text

    def test_serving_generate_rejects_model_exceeding_device_profile(self):
        """
        Validates Task T5: Device-profile enforcement (phone / limited device cannot run 70B).
        """
        from fastapi.testclient import TestClient
        from serving.server import create_serving_app

        engine = ModelServingEngine()
        # Register a huge model requiring 500GB RAM
        huge_model = ModelArtifact(model_id="llama3-70b", parameter_size="70B", min_ram_gb=500.0)
        engine.store.register_artifact(huge_model)

        app = create_serving_app(engine)
        client = TestClient(app)

        gen_res = client.post(
            "/generate",
            json={"model": "llama3-70b", "prompt": "Hi", "stream": False},
        )
        assert gen_res.status_code == 422
        assert "Device profile insufficient" in gen_res.json()["detail"]

