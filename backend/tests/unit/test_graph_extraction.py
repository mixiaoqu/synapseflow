from app.services.graph_extraction import _parse_graph_extraction_payload
from app.services.graph_models import GraphChunkRecord


def test_parse_graph_extraction_payload_returns_entities_and_relation_candidates():
    chunk = GraphChunkRecord(
        team_id=1,
        knowledge_base_id=2,
        document_id=3,
        document_chunk_id=4,
        chunk_index=0,
        document_title="系统说明",
        section_path="关系",
        content_hash="chunk-hash",
    )

    result = _parse_graph_extraction_payload(
        chunk=chunk,
        payload={
            "entities": [
                {
                    "name": "ProjectApp",
                    "type": "component",
                    "aliases": ["项目应用"],
                    "description": "项目应用入口",
                    "attributes": {"route": "/projects"},
                }
            ],
            "relations": [
                {
                    "source": "ProjectApp",
                    "source_type": "component",
                    "target": "AssistantProfile",
                    "target_type": "component",
                    "type": "calls",
                    "evidence_text": "ProjectApp 调用 AssistantProfile",
                    "confidence": 0.8,
                    "attributes": {"mode": "default"},
                }
            ],
        },
    )

    assert result.entities[0].name == "ProjectApp"
    assert result.entities[0].entity_type == "COMPONENT"
    assert result.entities[0].description == "项目应用入口"
    assert result.relation_candidates[0].source_name == "ProjectApp"
    assert result.relation_candidates[0].target_name == "AssistantProfile"
    assert result.relation_candidates[0].relation_type == "CALLS"
    assert result.relation_candidates[0].confidence == 0.8


def test_parse_graph_extraction_payload_adds_search_aliases_for_code_symbol():
    chunk = GraphChunkRecord(
        team_id=1,
        knowledge_base_id=67,
        document_id=3,
        document_chunk_id=4,
        chunk_index=0,
        document_title="bin.parseAddress.js",
        section_path="",
        content_hash="chunk-hash",
    )

    result = _parse_graph_extraction_payload(
        chunk=chunk,
        payload={
            "entities": [
                {
                    "name": "batchUpdateUserData",
                    "type": "operation",
                    "qualified_name": "bin/parseAddress.js::batchUpdateUserData",
                    "aliases": [],
                    "description": "函数操作 bin/parseAddress.js::batchUpdateUserData",
                    "attributes": {},
                }
            ],
            "relations": [],
        },
    )

    aliases = set(result.entities[0].aliases)
    assert "batch update user data" in aliases
    assert "update user data" in aliases
    assert "parseAddress.js batchUpdateUserData" in aliases
    assert "parse address batch update user data" in aliases
    assert "bin/parseAddress.js::batchUpdateUserData" not in aliases
    assert result.entities[0].canonical_name == "bin/parseAddress.js::batchUpdateUserData"
    assert result.entities[0].attributes["qualified_name"] == "bin/parseAddress.js::batchUpdateUserData"
