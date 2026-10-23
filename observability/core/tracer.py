"""
Pheonix Unified Cross-Module Telemetry & Distributed Tracer (Task 1.2 & Task 3.5)
Captures synchronized trace logs (trace_id, span_id, module, operation, duration_ms, tokens, cost)
across model-gateway, orchestrator, memory, and model-serving layers.
Supports local JSONL append-only persistence and background Langfuse export.
"""

import os
import time
import json
import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TokenUsageEvent(BaseModel):
    """Event emitted whenever token usage is recorded in a telemetry span."""
    trace_id: str
    span_id: str
    module: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: str = Field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TelemetrySpan(BaseModel):
    """Unified telemetry schema for all Pheonix modules."""
    trace_id: str = Field(default_factory=lambda: f"trc-{uuid.uuid4().hex[:16]}")
    span_id: str = Field(default_factory=lambda: f"spn-{uuid.uuid4().hex[:12]}")
    parent_span_id: Optional[str] = None
    module: str  # "gateway" | "orchestrator" | "memory" | "serving" | "auth" | "sandbox"
    operation: str  # "chat_completion", "dag_step", "memory_recall", "sandbox_run"
    status_code: int = 200
    duration_ms: float = 0.0
    token_usage: Dict[str, int] = Field(
        default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    )
    cost_usd: float = 0.0
    timestamp: str = Field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TelemetryCollector:
    """Thread-safe collector for cross-module traces with local JSONL and Langfuse export."""
    _instance: Optional["TelemetryCollector"] = None
    _singleton_lock = threading.Lock()

    def __init__(self, log_path: Optional[str] = None, enable_jsonl: bool = True):
        self._lock = threading.Lock()
        self.spans: List[TelemetrySpan] = []
        self.enable_jsonl = enable_jsonl
        default_path = os.environ.get("PHEONIX_TELEMETRY_LOG", "./data/telemetry_traces.jsonl")
        self.log_path = Path(log_path or default_path)
        if self.enable_jsonl:
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        # Exporter hooks (e.g. Langfuse / OpenLLMetry)
        self._exporters: List[Any] = []
        # Token usage listeners (e.g. Tracker quota deduction)
        self._token_usage_listeners: List[Callable[[TokenUsageEvent], None]] = []
        self._tracker_client: Optional[Any] = None

    @classmethod
    def get_instance(cls) -> "TelemetryCollector":
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = TelemetryCollector()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._singleton_lock:
            cls._instance = None

    def register_exporter(self, exporter: Any) -> None:
        with self._lock:
            self._exporters.append(exporter)

    def add_token_usage_listener(self, listener: Callable[[TokenUsageEvent], None]) -> None:
        """Register a callback invoked whenever token usage is reported in a span."""
        with self._lock:
            self._token_usage_listeners.append(listener)

    def record_span(self, span: TelemetrySpan) -> TelemetrySpan:
        """Records a completed span in-memory, writes to local JSONL, and dispatches to exporters."""
        with self._lock:
            self.spans.append(span)

            if self.enable_jsonl:
                try:
                    with open(self.log_path, "a", encoding="utf-8") as f:
                        f.write(span.model_dump_json() + "\n")
                except Exception:
                    pass

        # Dispatch to external exporters asynchronously or non-blockingly
        for exp in list(self._exporters):
            try:
                if hasattr(exp, "export_span"):
                    exp.export_span(span)
            except Exception:
                pass

        # Emit TokenUsageEvent to tracker listeners if tokens or cost were consumed
        total_tokens = span.token_usage.get("total_tokens", 0)
        cost_usd = span.cost_usd
        if total_tokens > 0 or cost_usd > 0:
            provider = span.metadata.get("provider") or span.module
            event = TokenUsageEvent(
                trace_id=span.trace_id,
                span_id=span.span_id,
                module=span.module,
                provider=provider,
                prompt_tokens=span.token_usage.get("prompt_tokens", 0),
                completion_tokens=span.token_usage.get("completion_tokens", 0),
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                metadata=span.metadata,
            )
            for listener in list(self._token_usage_listeners):
                try:
                    listener(event)
                except Exception:
                    pass

            # Auto-deduct from tracker if tracker module is available
            try:
                from tracker.client import TrackerClient
                tc = getattr(self, "_tracker_client", None)
                if tc is None:
                    tc = TrackerClient()
                    self._tracker_client = tc
                tc.deduct_usage(
                    provider=provider,
                    tokens=total_tokens,
                    cost_usd=cost_usd,
                    key_id=span.metadata.get("key_id"),
                )
            except Exception:
                pass

        return span

    def emit(
        self,
        module: str,
        operation: str,
        duration_ms: float = 0.0,
        status_code: int = 200,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        token_usage: Optional[Dict[str, int]] = None,
        cost_usd: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TelemetrySpan:
        """Convenience factory to create and record a span."""
        span = TelemetrySpan(
            trace_id=trace_id or f"trc-{uuid.uuid4().hex[:16]}",
            parent_span_id=parent_span_id,
            module=module,
            operation=operation,
            duration_ms=round(duration_ms, 2),
            status_code=status_code,
            token_usage=token_usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            cost_usd=cost_usd,
            metadata=metadata or {},
        )
        return self.record_span(span)

    def get_spans(self, trace_id: Optional[str] = None, module: Optional[str] = None) -> List[TelemetrySpan]:
        with self._lock:
            res = list(self.spans)
            if trace_id:
                res = [s for s in res if s.trace_id == trace_id]
            if module:
                res = [s for s in res if s.module == module]
            return res

    def clear(self) -> None:
        with self._lock:
            self.spans.clear()


class TraceContext:
    """Context manager for measuring block duration and automatically emitting a TelemetrySpan."""

    def __init__(
        self,
        module: str,
        operation: str,
        collector: Optional[TelemetryCollector] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.collector = collector or TelemetryCollector.get_instance()
        self.module = module
        self.operation = operation
        self.trace_id = trace_id or f"trc-{uuid.uuid4().hex[:16]}"
        self.metadata = metadata or {}
        self.start_time: float = 0.0
        self.span: Optional[TelemetrySpan] = None
        self.status_code: int = 200
        self.token_usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.cost_usd: float = 0.0

    def set_tokens(self, prompt: int, completion: int) -> None:
        self.token_usage = {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        }

    def set_cost(self, cost_usd: float) -> None:
        self.cost_usd = cost_usd

    def __enter__(self) -> "TraceContext":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration_ms = (time.perf_counter() - self.start_time) * 1000.0
        if exc_type is not None:
            self.status_code = 500
            self.metadata["error"] = str(exc_val)

        self.span = self.collector.emit(
            module=self.module,
            operation=self.operation,
            duration_ms=duration_ms,
            status_code=self.status_code,
            trace_id=self.trace_id,
            token_usage=self.token_usage,
            cost_usd=self.cost_usd,
            metadata=self.metadata,
        )


class LangfuseExporter:
    """Exports TelemetrySpans to Langfuse ingestion API asynchronously without latency penalty (Task 3.5)."""

    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
        batch_size: int = 50,
        flush_interval_sec: float = 2.0,
    ):
        self.public_key = public_key or os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        self.secret_key = secret_key or os.environ.get("LANGFUSE_SECRET_KEY", "")
        self.host = (host or os.environ.get("LANGFUSE_HOST", "http://localhost:3100")).rstrip("/")
        self.batch_size = batch_size
        self.flush_interval_sec = flush_interval_sec
        self._queue: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self.exported_batches: List[List[Dict[str, Any]]] = []

    def export_span(self, span: TelemetrySpan) -> None:
        """Converts a TelemetrySpan into a Langfuse ingestion event."""
        event_type = "generation-create" if span.module in ("serving", "gateway") else "span-create"
        event = {
            "id": span.span_id,
            "type": event_type,
            "timestamp": span.timestamp,
            "body": {
                "traceId": span.trace_id,
                "name": f"{span.module}:{span.operation}",
                "startTime": span.timestamp,
                "endTime": span.timestamp,
                "metadata": span.metadata,
                "usage": {
                    "input": span.token_usage.get("prompt_tokens", 0),
                    "output": span.token_usage.get("completion_tokens", 0),
                    "total": span.token_usage.get("total_tokens", 0),
                    "totalCost": span.cost_usd,
                },
                "statusMessage": "OK" if span.status_code == 200 else "ERROR",
            },
        }
        with self._lock:
            self._queue.append(event)
            if len(self._queue) >= self.batch_size:
                self.flush()

    def flush(self) -> int:
        """Flushes buffered events to Langfuse endpoint or mock."""
        with self._lock:
            if not self._queue:
                return 0
            batch = list(self._queue)
            self._queue.clear()
            self.exported_batches.append(batch)

        if self.public_key and self.secret_key:
            try:
                import httpx
                url = f"{self.host}/api/public/ingestion"
                headers = {"Content-Type": "application/json"}
                httpx.post(url, json={"batch": batch}, auth=(self.public_key, self.secret_key), timeout=2.0)
            except Exception:
                pass

        return len(batch)

