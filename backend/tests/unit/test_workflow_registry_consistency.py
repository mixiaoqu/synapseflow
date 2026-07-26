import json
import re
from pathlib import Path

import pytest

from app.agents.runtime.factory import _build_registry
from app.application.agent.workflow_meta import WORKFLOW_NODE_META

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_ROOT.parent


@pytest.mark.parametrize("graph_id,definition", _build_registry().items())
def test_compiled_graph_nodes_match_registry_and_workflow_meta(graph_id, definition):
    compiled_graph = definition.build()
    compiled_node_ids = set(compiled_graph.get_graph().nodes) - {"__start__", "__end__"}
    registered_node_ids = set(definition.node_ids)

    assert compiled_node_ids == registered_node_ids
    assert set(WORKFLOW_NODE_META[graph_id]) == registered_node_ids


def test_langgraph_entries_point_to_registered_graph_factories():
    config = json.loads((BACKEND_ROOT / "langgraph.json").read_text(encoding="utf-8"))
    registry = _build_registry()
    exposed_graph_ids = {
        graph_id for graph_id, definition in registry.items() if definition.expose_in_langgraph
    }

    assert set(config["graphs"]) == exposed_graph_ids

    for graph_id, entrypoint in config["graphs"].items():
        definition = registry[graph_id]
        module_path, function_name = entrypoint.split(":", maxsplit=1)

        assert function_name == definition.factory.__name__
        assert module_path.endswith(definition.factory.__module__.replace(".", "/") + ".py")


def test_architecture_document_node_lists_match_registry():
    content = (REPOSITORY_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    block = content.split("<!-- workflow-node-ids:start -->", maxsplit=1)[1].split(
        "<!-- workflow-node-ids:end -->", maxsplit=1
    )[0]
    documented_nodes = {
        graph_id: tuple(re.findall(r"`([^`]+)`", nodes_text))
        for graph_id, nodes_text in re.findall(r"- `([^`]+)` nodes: (.+)", block)
    }

    assert documented_nodes == {
        graph_id: definition.node_ids for graph_id, definition in _build_registry().items()
    }
