import asyncio

from app.services.graph_summary import (
    build_entity_summary_prompt,
    build_relation_summary_prompt,
    refresh_entity_summaries,
    refresh_relation_summaries,
)


def test_build_entity_summary_prompt_includes_context_payload():
    prompt = build_entity_summary_prompt(
        {
            "normalized_name": "projectapp",
            "display_name": "ProjectApp",
            "entity_type": "COMPONENT",
            "aliases": ["Project App"],
            "entity_props": {"attr_owner": "平台组"},
            "mentions": [
                {
                    "document_title": "系统说明",
                    "section_path": "绑定关系",
                    "evidence": "ProjectApp 默认绑定 AssistantProfile",
                    "mention_props": {"team_id": 1, "attr_owner": "平台组"},
                }
            ],
            "relations": [
                {
                    "other": "AssistantProfile",
                    "relation_type": "USES",
                    "evidence": "ProjectApp 默认绑定 AssistantProfile",
                    "relation_props": {"team_id": 1, "knowledge_base_id": 2},
                }
            ],
        }
    )

    assert "ProjectApp" in prompt
    assert "平台组" in prompt
    assert "USES" in prompt


def test_refresh_entity_summaries_writes_generated_summary(monkeypatch):
    calls = []

    class FakeStore:
        async def list_entity_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names):
            calls.append(("list", knowledge_base_id, team_id, normalized_names))
            return [
                {
                    "normalized_name": "projectapp",
                    "display_name": "ProjectApp",
                    "entity_type": "COMPONENT",
                    "aliases": ["Project App"],
                    "entity_props": {"attr_owner": "平台组"},
                    "mentions": [
                        {
                            "document_title": "系统说明",
                            "section_path": "绑定关系",
                            "evidence": "ProjectApp 默认绑定 AssistantProfile",
                            "mention_props": {"team_id": 1, "knowledge_base_id": 2, "attr_owner": "平台组"},
                        }
                    ],
                    "relations": [],
                }
            ]

        async def upsert_entity_summaries(self, rows):
            calls.append(("upsert", rows))

    class FakeLLM:
        async def ainvoke(self, prompt):
            assert "ProjectApp" in prompt
            return type("Resp", (), {"content": "ProjectApp 是用于绑定 AssistantProfile 的组件。"})

    summary_count = asyncio.run(
        refresh_entity_summaries(
            store=FakeStore(),
            knowledge_base_id=2,
            team_id=1,
            normalized_names=["projectapp"],
            llm_factory=lambda: FakeLLM(),
        )
    )

    assert summary_count == 1
    assert calls[0] == ("list", 2, 1, ["projectapp"])
    assert calls[1][0] == "upsert"
    assert calls[1][1][0]["summary"] == "ProjectApp 是用于绑定 AssistantProfile 的组件。"


def test_build_relation_summary_prompt_includes_context_payload():
    prompt = build_relation_summary_prompt(
        {
            "source_display_name": "ProjectApp",
            "target_display_name": "AssistantProfile",
            "relation_type": "USES",
            "evidence": "ProjectApp 默认绑定 AssistantProfile",
            "relation_props": {"attr_mode": "auto"},
        }
    )

    assert "ProjectApp" in prompt
    assert "AssistantProfile" in prompt
    assert "USES" in prompt


def test_refresh_relation_summaries_writes_generated_summary(monkeypatch):
    calls = []

    class FakeStore:
        async def list_relation_summary_contexts(self, *, knowledge_base_id, team_id, document_id=None):
            calls.append(("list", knowledge_base_id, team_id, document_id))
            return [
                {
                    "source_normalized_name": "projectapp",
                    "source_display_name": "ProjectApp",
                    "source_entity_type": "COMPONENT",
                    "source_aliases": [],
                    "source_props": {},
                    "target_normalized_name": "assistantprofile",
                    "target_display_name": "AssistantProfile",
                    "target_entity_type": "COMPONENT",
                    "target_aliases": [],
                    "target_props": {},
                    "relation_type": "USES",
                    "evidence": "ProjectApp 默认绑定 AssistantProfile",
                    "relation_props": {"attr_mode": "auto"},
                }
            ]

        async def upsert_relation_summaries(self, rows):
            calls.append(("upsert", rows))

    class FakeLLM:
        async def ainvoke(self, prompt):
            assert "ProjectApp" in prompt
            return type("Resp", (), {"content": "ProjectApp 通过默认绑定使用 AssistantProfile。"})

    summary_count = asyncio.run(
        refresh_relation_summaries(
            store=FakeStore(),
            knowledge_base_id=2,
            team_id=1,
            document_id=9,
            llm_factory=lambda: FakeLLM(),
        )
    )

    assert summary_count == 1
    assert calls[0] == ("list", 2, 1, 9)
    assert calls[1][0] == "upsert"
    assert calls[1][1][0]["summary"] == "ProjectApp 通过默认绑定使用 AssistantProfile。"
