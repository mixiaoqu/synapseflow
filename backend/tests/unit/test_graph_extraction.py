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
