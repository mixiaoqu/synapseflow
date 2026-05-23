from app.services.graph_models import (
    GraphChunkRecord,
    GraphEntityRecord,
    GraphRelationRecord,
)
from app.services.graph_normalizer import normalize_chunk_graph


def test_normalize_chunk_graph_filters_noise_and_dedupes_entities():
    chunk = GraphChunkRecord(
        team_id=1,
        knowledge_base_id=2,
        document_id=1,
        document_chunk_id=11,
        document_title="配置",
        section_path="数据库",
    )
    entities = [
        GraphEntityRecord(
            document_id=1,
            document_chunk_id=11,
            normalized_name="  PostgreSQL  ",
            display_name=" PostgreSQL ",
            entity_type="DATABASE",
            aliases=("Postgres",),
            attributes={"version": "15"},
            evidence="结果写入 PostgreSQL",
        ),
        GraphEntityRecord(
            document_id=1,
            document_chunk_id=11,
            normalized_name="postgresql",
            display_name="PostgreSQL",
            entity_type="DATABASE",
            aliases=(),
            attributes={"edition": "community"},
            evidence="结果写入 PostgreSQL",
        ),
        GraphEntityRecord(
            document_id=1,
            document_chunk_id=11,
            normalized_name="系统",
            display_name="系统",
            entity_type="OTHER",
            aliases=(),
            attributes={},
            evidence="系统",
        ),
    ]
    relations = [
        GraphRelationRecord(
            team_id=1,
            knowledge_base_id=2,
            document_id=1,
            document_chunk_id=11,
            source_normalized_name="postgresql",
            target_normalized_name="postgresql",
            relation_type="USES",
            attributes={"mode": "direct"},
            evidence="自引用",
        )
    ]

    normalized = normalize_chunk_graph(
        chunk=chunk,
        entities=entities,
        relations=relations,
    )

    assert [entity.normalized_name for entity in normalized.entities] == ["postgresql"]
    assert normalized.relations == []


def test_normalize_chunk_graph_keeps_valid_relations_and_maps_unknown_type():
    chunk = GraphChunkRecord(
        team_id=1,
        knowledge_base_id=2,
        document_id=2,
        document_chunk_id=22,
        document_title="组件关系",
        section_path=None,
    )
    entities = [
        GraphEntityRecord(
            document_id=2,
            document_chunk_id=22,
            normalized_name="projectapp",
            display_name="ProjectApp",
            entity_type="COMPONENT",
            aliases=(),
            attributes={"owner": "平台组"},
            evidence="ProjectApp 默认绑定 AssistantProfile",
        ),
        GraphEntityRecord(
            document_id=2,
            document_chunk_id=22,
            normalized_name="assistantprofile",
            display_name="AssistantProfile",
            entity_type="COMPONENT",
            aliases=(),
            attributes={"scope": "default"},
            evidence="ProjectApp 默认绑定 AssistantProfile",
        ),
    ]
    relations = [
        GraphRelationRecord(
            team_id=1,
            knowledge_base_id=2,
            document_id=2,
            document_chunk_id=22,
            source_normalized_name="projectapp",
            target_normalized_name="assistantprofile",
            relation_type="BINDS_TO",
            attributes={"mode": "auto"},
            evidence="ProjectApp 默认绑定 AssistantProfile",
        )
    ]

    normalized = normalize_chunk_graph(
        chunk=chunk,
        entities=entities,
        relations=relations,
    )

    assert normalized.relations[0].relation_type == "RELATED_TO"
    assert normalized.relations[0].attributes == {"mode": "auto"}
