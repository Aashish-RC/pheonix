"""Core data models for Canvas Graph and Live Artifacts."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Position(BaseModel):
    """2D spatial placement on the canvas board."""
    model_config = ConfigDict(extra="ignore")

    x: float = 0.0
    y: float = 0.0
    width: float = 320.0
    height: float = 240.0


class NodeType(str, Enum):
    TEXT = "text"
    ARTIFACT = "artifact"
    EXECUTION = "execution"
    FILE_REF = "file_ref"
    NOTE_REF = "note_ref"


class EdgeType(str, Enum):
    DEPENDENCY = "dependency"
    REFERENCE = "reference"
    DATA_FLOW = "data_flow"


class ArtifactType(str, Enum):
    CODE = "code"
    MARKDOWN = "markdown"
    HTML_PREVIEW = "html_preview"
    TABLE = "table"
    DIAGRAM = "diagram"


class CanvasNode(BaseModel):
    """Individual visual card or block on the canvas graph."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    board_id: UUID
    node_type: NodeType = NodeType.TEXT
    title: str = "Untitled Block"
    position: Position = Field(default_factory=Position)
    data: Dict[str, Any] = Field(default_factory=dict, description="Block content or payload")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CanvasEdge(BaseModel):
    """Directional connector edge between two canvas nodes."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    board_id: UUID
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType = EdgeType.REFERENCE
    label: Optional[str] = None


class CanvasBoard(BaseModel):
    """2D Canvas workspace containing spatial nodes and connectors."""
    model_config = ConfigDict(extra="ignore")

    id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(default="default", description="Strict workspace boundary")
    name: str = "Default Canvas"
    viewport_x: float = 0.0
    viewport_y: float = 0.0
    zoom: float = 1.0
    nodes: List[CanvasNode] = Field(default_factory=list)
    edges: List[CanvasEdge] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ArtifactRevision(BaseModel):
    """Immutable snapshot of an artifact's state at a point in time."""
    model_config = ConfigDict(extra="ignore")

    version: int = 1
    content: str = ""
    author: str = "agent"  # 'agent' | 'user'
    diff_summary: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class Artifact(BaseModel):
    """Versioned live artifact container with time-travel snapshots."""
    model_config = ConfigDict(extra="ignore")

    id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(default="default")
    artifact_type: ArtifactType = ArtifactType.CODE
    title: str = "Untitled Artifact"
    current_version: int = 1
    revisions: List[ArtifactRevision] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def current_content(self) -> str:
        if self.revisions:
            return self.revisions[-1].content
        return ""


class ExecutionResult(BaseModel):
    """Output state of a runnable execution card."""
    model_config = ConfigDict(extra="ignore")

    card_id: str
    status: str = "success"  # 'success' | 'error' | 'timeout'
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    executed_at: datetime = Field(default_factory=utc_now)
