from app.services.graph_models import (
    GraphChunkRecord,
    GraphEntityRecord,
    GraphRelationCandidate,
    build_entity_id,
)
from app.services.graph_normalizer import normalize_chunk_graph


def _entity(*, name: str, entity_type: str, aliases=(), attributes=None):
    return GraphEntityRecord(
        id=build_entity_id(team_id=1, knowledge_base_id=2, entity_type=entity_type, name=name),
        team_id=1,
        knowledge_base_id=2,
        name=name,
        entity_type=entity_type,
        aliases=tuple(aliases),
        attributes=attributes or {},
    )


def test_normalize_chunk_graph_merges_same_type_and_name_only():
    chunk = GraphChunkRecord(
        team_id=1,
        knowledge_base_id=2,
        document_id=9,
        document_chunk_id=11,
        chunk_index=0,
        document_title="关系说明",
        section_path="模块",
    )
    normalized = normalize_chunk_graph(
        chunk=chunk,
        entities=[
            _entity(name="Payment", entity_type="MODULE", aliases=("支付模块",), attributes={"owner": "A"}),
            _entity(name="Payment", entity_type="MODULE", aliases=("Settlement",), attributes={"domain": "billing"}),
            _entity(name="Payment", entity_type="STATUS"),
            _entity(name="系统", entity_type="OTHER"),
        ],
        relation_candidates=[
            GraphRelationCandidate(
                source_name="Payment",
                source_entity_type="MODULE",
                target_name="Payment",
                target_entity_type="STATUS",
                relation_type="HAS_STATUS",
                evidence_text="Payment 有状态 Payment",
            )
        ],
    )

    assert len(normalized.entities) == 2
    module_entity = next(entity for entity in normalized.entities if entity.entity_type == "MODULE")
    assert module_entity.aliases == ("支付模块", "Settlement")
    assert module_entity.attributes == {"owner": "A", "domain": "billing"}
    assert len(normalized.relation_candidates) == 1


def test_normalize_chunk_graph_drops_relation_without_resolved_entities():
    chunk = GraphChunkRecord(
        team_id=1,
        knowledge_base_id=2,
        document_id=9,
        document_chunk_id=12,
        chunk_index=1,
        document_title="依赖说明",
        section_path=None,
    )
    normalized = normalize_chunk_graph(
        chunk=chunk,
        entities=[_entity(name="ProjectApp", entity_type="COMPONENT")],
        relation_candidates=[
            GraphRelationCandidate(
                source_name="ProjectApp",
                source_entity_type="COMPONENT",
                target_name="AssistantProfile",
                target_entity_type="COMPONENT",
                relation_type="CALLS",
                evidence_text="ProjectApp calls AssistantProfile",
            )
        ],
    )

    assert normalized.entities[0].name == "ProjectApp"
    assert normalized.relation_candidates == []
