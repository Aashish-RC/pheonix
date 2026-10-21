"""
Pheonix Local Runtime Adapter Base Interface
Abstract definition for local inference engines (Ollama, llama.cpp, LocalAI, etc.)
"""

from abc import ABC, abstractmethod
from typing import List
from ..models import InferenceRequest, InferenceResponse


class LocalRuntimeAdapter(ABC):
    """Abstract interface all local model serving runtimes must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the runtime adapter (e.g. 'ollama', 'llama.cpp', 'mock')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Probes whether the local runtime daemon or process is reachable."""
        pass

    @abstractmethod
    def list_models(self) -> List[str]:
        """Lists active models currently loaded or available in this runtime."""
        pass

    @abstractmethod
    def chat_completion(self, request: InferenceRequest) -> InferenceResponse:
        """Executes local chat completion."""
        pass
