from app.agents.common.document_analysis import (
    build_markdown_section_tree,
    parse_markdown_headings,
)
from app.agents.common.retrieval import pick_query_from_state


def test_pick_query_from_state_returns_first_non_empty_candidate():
    state = {
        "query": "   ",
        "optimized_query": "normalized question",
        "fallback_query": "backup question",
    }

    assert (
        pick_query_from_state(state, "query", "optimized_query", "fallback_query")
        == "normalized question"
    )


def test_parse_markdown_headings_and_build_section_tree():
    document = "\n".join(
        [
            "# Product Overview",
            "Intro",
            "## Core Flow",
            "Flow details",
            "### Empty State",
            "Fallback details",
            "## Admin Panel",
            "Admin details",
        ]
    )

    headings = parse_markdown_headings(document)
    tree = build_markdown_section_tree(headings, document_length=len(document))

    assert [heading["title"] for heading in headings] == [
        "Product Overview",
        "Core Flow",
        "Empty State",
        "Admin Panel",
    ]
    assert len(tree) == 1
    assert tree[0]["title"] == "Product Overview"
    assert len(tree[0]["children"]) == 2
    assert tree[0]["children"][0]["title"] == "Core Flow"
    assert tree[0]["children"][0]["children"][0]["title"] == "Empty State"
    assert tree[0]["children"][1]["title"] == "Admin Panel"
