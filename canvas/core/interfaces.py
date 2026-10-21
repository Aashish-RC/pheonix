"""Abstract Base Classes for Canvas Graph, Artifacts, and Card Execution."""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from .models import (
    Artifact,
    ArtifactType,
    CanvasBoard,
    CanvasEdge,
    CanvasNode,
    ExecutionResult,
    Position,
)


class BaseCanvasStore(ABC):
    """Abstract interface for managing canvas boards, nodes, and spatial edges."""

    @abstractmethod
    def save_board(self, board: CanvasBoard) -> CanvasBoard:
        """Create or update a canvas board."""
        pass

    @abstractmethod
    def get_board(self, board_id: UUID, project_id: Optional[str] = None) -> Optional[CanvasBoard]:
        """Fetch a canvas board with all its nodes and edges."""
        pass

    @abstractmethod
    def list_boards(self, project_id: str = "default") -> List[CanvasBoard]:
        """List all canvas boards in a project."""
        pass

    @abstractmethod
    def delete_board(self, board_id: UUID) -> bool:
        """Permanently delete a canvas board."""
        pass

    @abstractmethod
    def add_node(self, board_id: UUID, node: CanvasNode) -> CanvasNode:
        """Add a card/block node to the canvas board."""
        pass

    @abstractmethod
    def update_node_position(self, board_id: UUID, node_id: str, position: Position) -> bool:
        """Update 2D spatial coordinates of a node."""
        pass

    @abstractmethod
    def delete_node(self, board_id: UUID, node_id: str) -> bool:
        """Remove a node and any connected edges from the board."""
        pass

    @abstractmethod
    def add_edge(self, board_id: UUID, edge: CanvasEdge) -> CanvasEdge:
        """Create a connector edge between two nodes."""
        pass

    @abstractmethod
    def delete_edge(self, board_id: UUID, edge_id: str) -> bool:
        """Remove a connector edge."""
        pass


class BaseArtifactManager(ABC):
    """Abstract interface for versioned live artifacts and time-travel snapshots."""

    @abstractmethod
    def create_artifact(
        self,
        project_id: str,
        title: str,
        artifact_type: ArtifactType,
        initial_content: str,
        author: str = "agent",
    ) -> Artifact:
        """Initialize an artifact container with version 1."""
        pass

    @abstractmethod
    def get_artifact(self, artifact_id: UUID) -> Optional[Artifact]:
        """Retrieve an artifact with complete revision history."""
        pass

    @abstractmethod
    def list_artifacts(self, project_id: str = "default") -> List[Artifact]:
        """List all artifacts within a project."""
        pass

    @abstractmethod
    def update_artifact(
        self,
        artifact_id: UUID,
        new_content: str,
        author: str = "agent",
        diff_summary: Optional[str] = None,
    ) -> Artifact:
        """Append a new revision snapshot to the artifact."""
        pass

    @abstractmethod
    def rollback_artifact(self, artifact_id: UUID, target_version: int) -> Artifact:
        """Revert the artifact to a prior version state."""
        pass

    @abstractmethod
    def delete_artifact(self, artifact_id: UUID) -> bool:
        """Permanently delete an artifact."""
        pass


class BaseCardExecutor(ABC):
    """Abstract interface for sandboxed execution cards."""

    @abstractmethod
    def execute_python(self, card_id: str, code: str, timeout_seconds: float = 5.0) -> ExecutionResult:
        """Execute sandboxed Python code and return captured outputs."""
        pass

    @abstractmethod
    def execute_command(self, card_id: str, command: str, timeout_seconds: float = 5.0) -> ExecutionResult:
        """Execute a safe shell command and return captured outputs."""
        pass
