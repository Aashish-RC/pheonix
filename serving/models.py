"""
Pheonix Model Serving Data Models
Defines hardware profiles, model artifacts, resource boundaries, and inference payloads.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


AccelerationBackend = Literal["cuda", "rocm", "metal", "directml", "cpu"]
GpuVendor = Literal["nvidia", "amd", "apple", "intel", "none"]
QuantizationFormat = Literal["Q4_K_M", "Q5_K_M", "Q8_0", "F16", "FP8", "safetensors"]


class DeviceProfile(BaseModel):
    """Host machine hardware specification and acceleration capabilities."""
    cpu_brand: str = "Unknown CPU"
    physical_cores: int = 4
    logical_cores: int = 8
    total_ram_gb: float = 16.0
    available_ram_gb: float = 8.0
    gpu_vendor: GpuVendor = "none"
    gpu_name: Optional[str] = None
    total_vram_gb: float = 0.0
    available_vram_gb: float = 0.0
    acceleration: AccelerationBackend = "cpu"
    max_recommended_parameters_billion: float = 3.0


class ModelArtifact(BaseModel):
    """Metadata describing a locally cached or available quantized model."""
    model_id: str
    parameter_size: str = "3B"
    format: str = "GGUF"
    quantization: QuantizationFormat = "Q4_K_M"
    file_path: Optional[str] = None
    file_size_bytes: int = 0
    min_ram_gb: float = 4.0
    min_vram_gb: float = 0.0
    context_length: int = 4096


class ResourceLimits(BaseModel):
    """Boundaries governing host memory and concurrency to avoid machine lockups."""
    max_ram_usage_percent: float = Field(default=98.0, ge=10.0, le=99.9)
    max_vram_usage_percent: float = Field(default=98.0, ge=10.0, le=99.9)
    max_cpu_threads: int = Field(default=4, ge=1)
    max_concurrent_streams: int = Field(default=2, ge=1)
    enforce_ram_limits: bool = True


class InferenceRequest(BaseModel):
    """Standardized inference request for local model execution."""
    model: str
    messages: List[Dict[str, Any]]
    temperature: float = 0.7
    max_tokens: int = 512
    stream: bool = False


class InferenceResponse(BaseModel):
    """Standardized inference response returned from a local runtime."""
    id: str
    model: str
    runtime: str
    content: str
    offline: bool = True
    tokens_prompt: int = 0
    tokens_completion: int = 0
    latency_ms: float = 0.0
