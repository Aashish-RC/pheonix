"""Unit tests for Canvas Graph: Boards, Nodes, Edges, Spatial Coordinates, and Isolation."""

from uuid import uuid4
import pytest

from canvas.core.models import (
    CanvasBoard,
    CanvasEdge,
    CanvasNode,
    EdgeType,
    NodeType,
    Position,
)
from canvas.storage.sqlite_canvas import SQLiteCanvasStore


@pytest.fixture
def store():
    return SQLiteCanvasStore(db_path=":memory:")


def test_board_lifecycle(store):
    board_id = uuid4()
    board = CanvasBoard(
        id=board_id,
        project_id="proj-alpha",
        name="Architecture Diagram",
        viewport_x=100.5,
        viewport_y=200.0,
        zoom=1.25,
    )
    store.save_board(board)

    loaded = store.get_board(board_id, project_id="proj-alpha")
    assert loaded is not None
    assert loaded.id == board_id
    assert loaded.name == "Architecture Diagram"
    assert loaded.viewport_x == 100.5
    assert loaded.viewport_y == 200.0
    assert loaded.zoom == 1.25
    assert len(loaded.nodes) == 0
    assert len(loaded.edges) == 0

    # Project isolation check
    isolated = store.get_board(board_id, project_id="proj-beta")
    assert isolated is None


def test_nodes_and_spatial_coordinates(store):
    board = store.save_board(CanvasBoard(name="Sprint Board", project_id="proj-1"))
    
    node1 = CanvasNode(
        board_id=board.id,
        node_type=NodeType.TEXT,
        title="Welcome Card",
        position=Position(x=10.0, y=20.0, width=300.0, height=200.0),
        data={"body": "Hello Canvas"},
    )
    node2 = CanvasNode(
        board_id=board.id,
        node_type=NodeType.EXECUTION,
        title="Compute Card",
        position=Position(x=400.0, y=20.0, width=350.0, height=220.0),
        data={"code": "print('ok')"},
    )
    
    store.add_node(board.id, node1)
    store.add_node(board.id, node2)

    loaded = store.get_board(board.id)
    assert len(loaded.nodes) == 2

    # Update position of node1
    moved = store.update_node_position(
        board.id,
        node1.id,
        Position(x=50.0, y=100.0, width=320.0, height=240.0),
    )
    assert moved is True

    updated_board = store.get_board(board.id)
    moved_node = next(n for n in updated_board.nodes if n.id == node1.id)
    assert moved_node.position.x == 50.0
    assert moved_node.position.y == 100.0


def test_edges_and_cascade_node_deletion(store):
    board = store.save_board(CanvasBoard(name="Flow Board", project_id="proj-1"))
    
    n1 = store.add_node(board.id, CanvasNode(board_id=board.id, title="Step 1"))
    n2 = store.add_node(board.id, CanvasNode(board_id=board.id, title="Step 2"))
    n3 = store.add_node(board.id, CanvasNode(board_id=board.id, title="Step 3"))

    edge1 = CanvasEdge(
        board_id=board.id,
        source_node_id=n1.id,
        target_node_id=n2.id,
        edge_type=EdgeType.DEPENDENCY,
        label="depends_on",
    )
    edge2 = CanvasEdge(
        board_id=board.id,
        source_node_id=n2.id,
        target_node_id=n3.id,
        edge_type=EdgeType.DATA_FLOW,
        label="pipes_into",
    )
    store.add_edge(board.id, edge1)
    store.add_edge(board.id, edge2)

    loaded = store.get_board(board.id)
    assert len(loaded.edges) == 2

    # Deleting n2 must cascade delete both edge1 and edge2
    deleted = store.delete_node(board.id, n2.id)
    assert deleted is True

    loaded_after = store.get_board(board.id)
    assert len(loaded_after.nodes) == 2
    assert len(loaded_after.edges) == 0


def test_board_deletion_cascade(store):
    board = store.save_board(CanvasBoard(name="Temporary Canvas", project_id="proj-temp"))
    n1 = store.add_node(board.id, CanvasNode(board_id=board.id, title="Temp Node"))
    store.add_edge(
        board.id,
        CanvasEdge(board_id=board.id, source_node_id=n1.id, target_node_id=n1.id),
    )

    assert len(store.list_boards("proj-temp")) == 1
    deleted = store.delete_board(board.id)
    assert deleted is True
    assert len(store.list_boards("proj-temp")) == 0
    assert store.get_board(board.id) is None
