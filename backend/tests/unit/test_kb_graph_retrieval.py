import asyncio

from app.services.kb_graph_retrieval import GraphRetriever


class FakeGraphStore:
    async def search_relation_evidence_for_pairs(self, *, relation_pairs, knowledge_base_id, team_id, limit):
        assert relation_pairs == []
        return []

    async def search_relation_evidence_for_queries(self, *, relation_queries, knowledge_base_id, team_id, limit):
        assert relation_queries == []
        return []

    async def list_entity_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names):
        assert knowledge_base_id == 7
        assert team_id == 3
        assert normalized_names == ["Prescription Flow", "Payment"]
        return []

    async def list_relation_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names, document_id=None):
        assert knowledge_base_id == 7
        assert team_id == 3
        assert normalized_names == ["Prescription Flow", "Payment"]
        return [
            {
                "source_normalized_name": "prescription_flow",
                "source_display_name": "Prescription Flow",
                "source_entity_type": "WORKFLOW",
                "source_summary": "Prescription Flow manages the prescription lifecycle.",
                "target_normalized_name": "payment",
                "target_display_name": "Payment",
                "target_entity_type": "MODULE",
                "target_summary": "Payment handles order settlement.",
                "relation_type": "CONFIGURES",
                "summary": "Prescription Flow configures Payment.",
                "evidence": "Prescription Flow connects to Payment",
            }
        ]

    async def search_related_evidence(self, *, entity_names, knowledge_base_id, team_id, limit):
        assert knowledge_base_id == 7
        assert team_id == 3
        return [
            {
                "document_id": 10,
                "document_chunk_id": 20,
                "document_title": "Integration Guide",
                "section_path": "Payments",
                "chunk_text": "Prescription Flow connects to Payment through order settlement.",
                "relation_type": "CONFIGURES",
                "evidence": "Prescription Flow connects to Payment",
                "matched_entities": ["Prescription Flow", "Payment"],
            }
        ]

    async def search_relation_paths(
        self,
        *,
        entity_names,
        relation_pairs,
        relation_queries,
        knowledge_base_id,
        team_id,
        max_hops,
        limit,
    ):
        assert max_hops >= 1
        return []


class FailingGraphStore:
    async def search_relation_evidence_for_pairs(self, *, relation_pairs, knowledge_base_id, team_id, limit):
        raise RuntimeError("neo4j unavailable")

    async def search_relation_evidence_for_queries(self, *, relation_queries, knowledge_base_id, team_id, limit):
        raise RuntimeError("neo4j unavailable")

    async def list_entity_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names):
        raise RuntimeError("neo4j unavailable")

    async def list_relation_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names, document_id=None):
        raise RuntimeError("neo4j unavailable")

    async def search_related_evidence(self, *, entity_names, knowledge_base_id, team_id, limit):
        raise RuntimeError("neo4j unavailable")

    async def search_relation_paths(self, **kwargs):
        raise RuntimeError("neo4j unavailable")


def test_graph_retriever_returns_normalized_docs_and_trace():
    result = asyncio.run(
        GraphRetriever(store=FakeGraphStore(), enabled=True).retrieve(
            candidate_entities=["Prescription Flow", "Payment"],
            relation_pairs=[],
            relation_queries=[],
            knowledge_base_id=7,
            team_id=3,
        )
    )

    text_fact = result["graph_facts"]["text"][0]
    relation_fact = result["graph_facts"]["relations"][0]
    evidence_fact = result["graph_facts"]["evidence"][0]
    entity_facts = result["graph_facts"]["entities"]
    assert text_fact["content"] == "Prescription Flow configures Payment."
    assert text_fact["document_id"] == 10
    assert "chunk_index" not in text_fact
    assert relation_fact["relation_type"] == "CONFIGURES"
    assert [item["display_name"] for item in entity_facts] == ["Prescription Flow", "Payment"]
    assert evidence_fact["evidence"] == "Prescription Flow connects to Payment"
    assert evidence_fact["fact_ref"] == {
        "source": "prescription_flow",
        "relation_type": "CONFIGURES",
        "target": "payment",
    }
    assert result["trace"]["graph_used"] is True
    assert result["trace"]["graph_hits"] == 5
    assert result["trace"]["graph_primary_hits"] == 1
    assert result["trace"]["graph_supporting_hits"] == 4
    assert result["trace"]["graph_mode"] == "relation_evidence"


def test_graph_retriever_degrades_when_disabled():
    result = asyncio.run(
        GraphRetriever(store=FakeGraphStore(), enabled=False).retrieve(
            candidate_entities=["Prescription Flow"],
            relation_pairs=[],
            relation_queries=[],
            knowledge_base_id=7,
            team_id=3,
        )
    )

    assert result["retrieved_docs"] == []
    assert result["trace"]["graph_used"] is False
    assert result["trace"]["empty_reason"] == "disabled"


def test_graph_retriever_degrades_on_store_error():
    result = asyncio.run(
        GraphRetriever(store=FailingGraphStore(), enabled=True).retrieve(
            candidate_entities=["Prescription Flow"],
            relation_pairs=[],
            relation_queries=[],
            knowledge_base_id=7,
            team_id=3,
        )
    )

    assert result["retrieved_docs"] == []
    assert result["trace"]["graph_used"] is True
    assert result["trace"]["empty_reason"] == "error"


def test_graph_retriever_uses_entity_summary_mode_for_definition_lookup():
    class SummaryGraphStore:
        async def list_entity_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names):
            assert normalized_names == ["Prescription Flow"]
            return [
                {
                    "normalized_name": "prescription flow",
                    "display_name": "Prescription Flow",
                    "entity_type": "PRODUCT",
                    "summary": "Prescription Flow handles the order lifecycle.",
                    "mentions": [],
                    "relations": [],
                }
            ]

        async def list_relation_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names, document_id=None):
            return []

        async def search_related_evidence(self, *, entity_names, knowledge_base_id, team_id, limit):
            return []

        async def search_relation_evidence_for_pairs(self, *, relation_pairs, knowledge_base_id, team_id, limit):
            return []

        async def search_relation_evidence_for_queries(self, *, relation_queries, knowledge_base_id, team_id, limit):
            return []

    result = asyncio.run(
        GraphRetriever(store=SummaryGraphStore(), enabled=True).retrieve(
            candidate_entities=["Prescription Flow"],
            relation_pairs=[],
            relation_queries=[],
            knowledge_base_id=7,
            team_id=3,
            question_type="definition_lookup",
        )
    )

    assert result["retrieved_docs"] == []
    assert result["graph_facts"]["text"] == []
    assert result["graph_facts"]["entities"][0]["display_name"] == "Prescription Flow"
    assert result["graph_facts"]["entities"][0]["summary"] == "Prescription Flow handles the order lifecycle."
    assert result["trace"]["graph_mode"] == "entity_summary"


def test_graph_retriever_respects_explicit_graph_mode():
    class MixedGraphStore:
        async def list_entity_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names):
            return [
                {
                    "normalized_name": "payment",
                    "display_name": "Payment",
                    "entity_type": "MODULE",
                    "summary": "Payment handles settlement.",
                    "mentions": [],
                    "relations": [],
                }
            ]

        async def list_relation_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names, document_id=None):
            raise AssertionError("relation summaries should not be queried in explicit entity_summary mode")

        async def search_related_evidence(self, *, entity_names, knowledge_base_id, team_id, limit):
            raise AssertionError("graph evidence should not be queried in explicit entity_summary mode")

        async def search_relation_evidence_for_pairs(self, *, relation_pairs, knowledge_base_id, team_id, limit):
            raise AssertionError("pair relation evidence should not be queried in explicit entity_summary mode")

        async def search_relation_evidence_for_queries(self, *, relation_queries, knowledge_base_id, team_id, limit):
            raise AssertionError("query relation evidence should not be queried in explicit entity_summary mode")

    result = asyncio.run(
        GraphRetriever(store=MixedGraphStore(), enabled=True).retrieve(
            candidate_entities=["Payment"],
            relation_pairs=[],
            relation_queries=[],
            knowledge_base_id=7,
            team_id=3,
            question_type="relationship_lookup",
            graph_mode="entity_summary",
        )
    )

    assert result["retrieved_docs"] == []
    assert result["graph_facts"]["entities"][0]["display_name"] == "Payment"
    assert result["trace"]["graph_mode"] == "entity_summary"


def test_graph_retriever_uses_relation_pairs_for_direct_relation_lookup():
    class PairGraphStore:
        async def list_entity_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names):
            return []

        async def list_relation_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names, document_id=None):
            return []

        async def search_related_evidence(self, *, entity_names, knowledge_base_id, team_id, limit):
            raise AssertionError("generic entity evidence should not be used when relation_pairs are provided")

        async def search_relation_evidence_for_pairs(self, *, relation_pairs, knowledge_base_id, team_id, limit):
            assert relation_pairs == [{"source": "project_app", "target": "assistant_profile"}]
            return [
                {
                    "document_id": 20,
                    "document_chunk_id": 30,
                    "document_title": "应用配置说明",
                    "section_path": "项目应用 / 助手配置",
                    "chunk_text": "项目应用需要先绑定助手配置。",
                    "relation_type": "REQUIRES_PERMISSION",
                    "evidence": "项目应用依赖助手配置。",
                    "matched_entities": ["项目应用", "助手配置"],
                }
            ]

        async def search_relation_evidence_for_queries(self, *, relation_queries, knowledge_base_id, team_id, limit):
            assert relation_queries == []
            return []

    result = asyncio.run(
        GraphRetriever(store=PairGraphStore(), enabled=True).retrieve(
            candidate_entities=["项目应用", "助手配置"],
            relation_pairs=[{"source": "project_app", "target": "assistant_profile"}],
            relation_queries=[],
            knowledge_base_id=7,
            team_id=3,
            question_type="relationship_lookup",
            graph_mode="relation_evidence",
        )
    )

    assert result["trace"]["graph_mode"] == "relation_evidence"
    assert result["graph_facts"]["text"][0]["document_title"] == "应用配置说明"
    assert result["graph_facts"]["relations"][0]["relation_type"] == "REQUIRES_PERMISSION"
    assert [item["display_name"] for item in result["graph_facts"]["entities"]] == ["项目应用", "助手配置"]
    assert result["graph_facts"]["evidence"][0]["fact_ref"] == {
        "source": "项目应用",
        "relation_type": "REQUIRES_PERMISSION",
        "target": "助手配置",
    }
    assert result["trace"]["graph_hits"] == 5
    assert result["trace"]["graph_primary_hits"] == 1
    assert result["trace"]["graph_supporting_hits"] == 4


def test_graph_retriever_uses_relation_query_for_outgoing_child_lookup():
    class QueryGraphStore:
        async def list_entity_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names):
            return []

        async def list_relation_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names, document_id=None):
            return []

        async def search_related_evidence(self, *, entity_names, knowledge_base_id, team_id, limit):
            raise AssertionError("generic entity evidence should not be used when relation_queries are provided")

        async def search_relation_evidence_for_pairs(self, *, relation_pairs, knowledge_base_id, team_id, limit):
            assert relation_pairs == []
            return []

        async def search_relation_evidence_for_queries(self, *, relation_queries, knowledge_base_id, team_id, limit):
            assert relation_queries == [
                {
                    "anchor_entity": "user",
                    "relation_hint": "下一级",
                    "relation_category": "hierarchy_child",
                    "direction": "outgoing",
                    "target_entity": None,
                }
            ]
            return [
                {
                    "document_id": 21,
                    "document_chunk_id": 31,
                    "document_title": "组织结构说明",
                    "section_path": "用户 / 层级关系",
                    "chunk_text": "用户下一级是成员。",
                    "relation_type": "HAS_CHILD",
                    "evidence": "用户下一级是成员。",
                    "matched_entities": ["用户", "成员"],
                }
            ]

    result = asyncio.run(
        GraphRetriever(store=QueryGraphStore(), enabled=True).retrieve(
            candidate_entities=["用户"],
            relation_pairs=[],
            relation_queries=[
                {
                    "anchor_entity": "user",
                    "relation_hint": "下一级",
                    "relation_category": "hierarchy_child",
                    "direction": "outgoing",
                    "target_entity": None,
                }
            ],
            knowledge_base_id=7,
            team_id=3,
            question_type="relationship_lookup",
            graph_mode="relation_evidence",
        )
    )

    assert result["graph_facts"]["text"]
    assert result["graph_facts"]["evidence"][0]["evidence"] == "用户下一级是成员。"
    assert [item["display_name"] for item in result["graph_facts"]["entities"]] == ["用户", "成员"]


def test_graph_retriever_skips_summary_modes_without_grounded_entities():
    class CandidateOnlySummaryStore:
        async def list_entity_summary_contexts(self, **kwargs):  # pragma: no cover
            return []

        async def list_relation_summary_contexts(self, **kwargs):  # pragma: no cover
            return []

        async def search_related_evidence(self, **kwargs):  # pragma: no cover
            return []

        async def search_relation_evidence_for_pairs(self, **kwargs):
            return []

        async def search_relation_evidence_for_queries(self, **kwargs):
            return []

    result = asyncio.run(
        GraphRetriever(store=CandidateOnlySummaryStore(), enabled=True).retrieve(
            candidate_entities=["商品视频"],
            relation_pairs=[],
            relation_queries=[],
            knowledge_base_id=7,
            team_id=3,
            question_type="summary_lookup",
            graph_mode="neighborhood_summary",
        )
    )

    assert result["retrieved_docs"] == []
    assert result["trace"]["empty_reason"] == "no_hits"
    assert result["trace"]["graph_hits"] == 0


def test_graph_retriever_filters_relation_summary_by_grounded_entities():
    class NeighborhoodSummaryStore:
        async def list_entity_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names):
            assert normalized_names == ["商品视频"]
            return []

        async def list_relation_summary_contexts(
            self,
            *,
            knowledge_base_id,
            team_id,
            normalized_names,
            document_id=None,
        ):
            assert normalized_names == ["商品视频"]
            return [
                {
                    "source_normalized_name": "商品视频",
                    "source_display_name": "商品视频",
                    "target_normalized_name": "上传限制",
                    "target_display_name": "上传限制",
                    "relation_type": "LIMITED_BY",
                    "summary": "商品视频受上传限制约束。",
                    "source_summary": "商品视频用于商品详情展示。",
                    "target_summary": "上传限制定义格式、大小和时长要求。",
                    "evidence": "商品视频 上传限制",
                }
            ]

        async def search_related_evidence(self, *, entity_names, knowledge_base_id, team_id, limit):
            assert entity_names == ["商品视频"]
            return []

        async def search_relation_evidence_for_pairs(self, *, relation_pairs, knowledge_base_id, team_id, limit):
            return []

        async def search_relation_evidence_for_queries(self, *, relation_queries, knowledge_base_id, team_id, limit):
            return []

    result = asyncio.run(
        GraphRetriever(store=NeighborhoodSummaryStore(), enabled=True).retrieve(
            candidate_entities=["商品视频"],
            relation_pairs=[],
            relation_queries=[],
            knowledge_base_id=7,
            team_id=3,
            question_type="summary_lookup",
            graph_mode="neighborhood_summary",
        )
    )

    assert result["trace"]["graph_mode"] == "neighborhood_summary"
    assert result["graph_facts"]["text"][0]["content"] == "商品视频受上传限制约束。"
    assert result["graph_facts"]["relations"]
    assert [item["display_name"] for item in result["graph_facts"]["entities"]] == ["商品视频", "上传限制"]


def test_graph_retriever_adds_multi_hop_paths_for_dependency_lookup():
    class PathGraphStore:
        async def list_entity_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names):
            return []

        async def list_relation_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names, document_id=None):
            return []

        async def search_related_evidence(self, *, entity_names, knowledge_base_id, team_id, limit):
            return []

        async def search_relation_evidence_for_pairs(self, *, relation_pairs, knowledge_base_id, team_id, limit):
            return []

        async def search_relation_evidence_for_queries(self, *, relation_queries, knowledge_base_id, team_id, limit):
            return []

        async def search_relation_paths(
            self,
            *,
            entity_names,
            relation_pairs,
            relation_queries,
            knowledge_base_id,
            team_id,
            max_hops,
            limit,
        ):
            assert entity_names == ["projectapp", "assistantprofile", "user"]
            assert max_hops == 3
            return [
                {
                    "path_id": "projectapp->assistantprofile->user",
                    "signature": "ProjectApp -[DEPENDS_ON]-> AssistantProfile -[CALLS]-> User",
                    "hop_count": 2,
                    "content": "ProjectApp 先依赖 AssistantProfile，再由 AssistantProfile 调用 User。",
                    "relation_types": ["DEPENDS_ON", "CALLS"],
                    "matched_entities": ["ProjectApp", "AssistantProfile", "User"],
                    "evidence": [
                        {
                            "relation_type": "DEPENDS_ON",
                            "evidence": "ProjectApp 默认绑定 AssistantProfile",
                            "document_title": "应用配置说明",
                            "section_path": "项目应用 / 助手配置",
                        },
                        {
                            "relation_type": "CALLS",
                            "evidence": "AssistantProfile 调用 User 服务完成身份读取",
                            "document_title": "调用链说明",
                            "section_path": "助手配置 / 依赖服务",
                        },
                    ],
                }
            ]

    result = asyncio.run(
        GraphRetriever(store=PathGraphStore(), enabled=True).retrieve(
            candidate_entities=["projectapp", "assistantprofile", "user"],
            relation_pairs=[],
            relation_queries=[],
            knowledge_base_id=7,
            team_id=3,
            question_type="dependency_lookup",
            graph_mode="relation_evidence",
            max_hops=3,
        )
    )

    assert result["graph_facts"]["paths"][0]["hop_count"] == 2
    assert result["graph_facts"]["paths"][0]["signature"] == (
        "ProjectApp -[DEPENDS_ON]-> AssistantProfile -[CALLS]-> User"
    )
    assert result["graph_facts"]["text"][0]["content"] == (
        "ProjectApp 先依赖 AssistantProfile，再由 AssistantProfile 调用 User。"
    )
    assert result["graph_facts"]["text"][0]["document_title"] == "应用配置说明"
    assert result["graph_facts"]["text"][0]["section_path"] == "项目应用 / 助手配置"
    assert result["trace"]["graph_hits"] == 2
    assert result["trace"]["graph_primary_hits"] == 1
    assert result["trace"]["graph_supporting_hits"] == 1
