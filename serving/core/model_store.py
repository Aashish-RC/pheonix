"""
Pheonix Local Model Store
Indexes and organizes local model weights, GGUF artifacts, and quantization specifications.
"""

from pathlib import Path
from typing import Dict, List, Optional
from ..models import ModelArtifact, QuantizationFormat


class ModelStore:
    """
    Manages local model repositories and artifact metadata.
    """

    def __init__(self, store_dir: Optional[Path] = None):
        self.store_dir = Path(store_dir or Path.home() / ".pheonix" / "models")
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._artifacts: Dict[str, ModelArtifact] = {}
        self._register_default_catalog()

    def _register_default_catalog(self) -> None:
        """Populates the catalog with known lightweight quantized models."""
        defaults = [
            ModelArtifact(
                model_id="llama3.2:1b",
                parameter_size="1B",
                format="GGUF",
                quantization="Q4_K_M",
                file_size_bytes=1_300_000_000,
                min_ram_gb=2.0,
                min_vram_gb=1.5,
                context_length=8192
            ),
            ModelArtifact(
                model_id="llama3.2:3b",
                parameter_size="3B",
                format="GGUF",
                quantization="Q4_K_M",
                file_size_bytes=2_000_000_000,
                min_ram_gb=3.5,
                min_vram_gb=2.5,
                context_length=8192
            ),
            ModelArtifact(
                model_id="phi3:mini",
                parameter_size="3.8B",
                format="GGUF",
                quantization="Q4_K_M",
                file_size_bytes=2_400_000_000,
                min_ram_gb=4.0,
                min_vram_gb=3.0,
                context_length=4096
            ),
            ModelArtifact(
                model_id="mistral:7b-instruct",
                parameter_size="7B",
                format="GGUF",
                quantization="Q4_K_M",
                file_size_bytes=4_400_000_000,
                min_ram_gb=8.0,
                min_vram_gb=6.0,
                context_length=8192
            ),
            ModelArtifact(
                model_id="qwen2.5:3b",
                parameter_size="3B",
                format="GGUF",
                quantization="Q4_K_M",
                file_size_bytes=2_100_000_000,
                min_ram_gb=3.5,
                min_vram_gb=2.5,
                context_length=32768
            ),
        ]
        for art in defaults:
            self._artifacts[art.model_id.lower()] = art

    def register_artifact(self, artifact: ModelArtifact) -> None:
        """Registers a new model artifact into the store."""
        self._artifacts[artifact.model_id.lower()] = artifact

    def get_artifact(self, model_id: str) -> Optional[ModelArtifact]:
        """Retrieves artifact details by model identifier."""
        return self._artifacts.get(model_id.lower())

    def list_artifacts(self) -> List[ModelArtifact]:
        """Returns all registered model artifacts."""
        return list(self._artifacts.values())

    def has_artifact(self, model_id: str) -> bool:
        """Checks if a model is registered in the store."""
        return model_id.lower() in self._artifacts
