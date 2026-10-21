"""
Pheonix Device Profiler
Inspects host machine hardware to establish memory and compute capabilities for local model execution.
"""

import os
import platform
import subprocess
import psutil
from typing import Optional
from ..models import DeviceProfile, AccelerationBackend, GpuVendor


class DeviceProfiler:
    """
    Automated hardware discovery for local model serving.
    Evaluates RAM, CPU cores, GPU VRAM, and compute backends.
    """

    @classmethod
    def profile(cls) -> DeviceProfile:
        """Inspects the current system and builds a comprehensive DeviceProfile."""
        cpu_brand = platform.processor() or platform.machine() or "Generic CPU"
        phys_cores = psutil.cpu_count(logical=False) or 4
        logical_cores = psutil.cpu_count(logical=True) or 8

        mem = psutil.virtual_memory()
        total_ram_gb = round(mem.total / (1024 ** 3), 2)
        avail_ram_gb = round(mem.available / (1024 ** 3), 2)

        gpu_vendor, gpu_name, vram_total, vram_avail, accel = cls._detect_gpu(total_ram_gb)
        max_params = cls._calculate_max_params(avail_ram_gb, vram_avail, accel)

        return DeviceProfile(
            cpu_brand=cpu_brand,
            physical_cores=phys_cores,
            logical_cores=logical_cores,
            total_ram_gb=total_ram_gb,
            available_ram_gb=avail_ram_gb,
            gpu_vendor=gpu_vendor,
            gpu_name=gpu_name,
            total_vram_gb=vram_total,
            available_vram_gb=vram_avail,
            acceleration=accel,
            max_recommended_parameters_billion=max_params
        )

    @classmethod
    def _detect_gpu(cls, total_ram_gb: float) -> tuple[GpuVendor, Optional[str], float, float, AccelerationBackend]:
        """Attempts to detect dedicated or integrated GPU accelerators."""
        # 1. NVIDIA via nvidia-smi
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=1.5
            )
            if result.returncode == 0 and result.stdout.strip():
                line = result.stdout.strip().split("\n")[0]
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    name = parts[0]
                    total_mb = float(parts[1])
                    free_mb = float(parts[2])
                    return "nvidia", name, round(total_mb / 1024, 2), round(free_mb / 1024, 2), "cuda"
        except Exception:
            pass

        # 2. Apple Silicon Metal detection
        if platform.system() == "Darwin" and platform.machine() == "arm64":
            # Apple unified memory: VRAM is shared with main RAM (~75% usable for Metal)
            unified_vram = round(total_ram_gb * 0.75, 2)
            return "apple", "Apple Silicon Unified GPU", unified_vram, unified_vram, "metal"

        # 3. DirectML / Intel / AMD fallback or CPU only
        return "none", None, 0.0, 0.0, "cpu"

    @classmethod
    def _calculate_max_params(cls, avail_ram: float, avail_vram: float, accel: AccelerationBackend) -> float:
        """Calculates maximum recommended model parameter size in billions for Q4_K_M quantization."""
        effective_mem = avail_vram if (accel in ["cuda", "metal", "rocm"] and avail_vram >= 4.0) else avail_ram

        if effective_mem >= 24.0:
            return 32.0
        elif effective_mem >= 12.0:
            return 14.0
        elif effective_mem >= 6.5:
            return 8.0
        elif effective_mem >= 3.5:
            return 3.0
        else:
            return 1.5
