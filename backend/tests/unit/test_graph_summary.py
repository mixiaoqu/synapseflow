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
            return type(
                "Resp",
                (),
                {
                    "content": {
                        "summaries": [
                            {
                                "normalized_name": "projectapp",
                                "summary": "ProjectApp 是用于绑定 AssistantProfile 的组件。",
                            }
                        ]
                    }
                },
            )

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


def test_refresh_entity_summaries_batches_contexts_and_reuses_llm(monkeypatch):
    calls = []
    factory_calls = []

    contexts = [
        {
            "normalized_name": f"entity-{index}",
            "display_name": f"Entity {index}",
            "entity_type": "FEATURE",
            "aliases": [],
            "entity_props": {},
            "mentions": [
                {
                    "document_title": "系统说明",
                    "section_path": "功能",
                    "evidence": f"Entity {index} evidence",
                    "mention_props": {},
                }
            ],
            "relations": [],
        }
        for index in range(9)
    ]

    class FakeStore:
        async def list_entity_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names):
            return contexts

        async def upsert_entity_summaries(self, rows):
            calls.append(("upsert", rows))

    class FakeLLM:
        async def ainvoke(self, prompt):
            calls.append(("prompt", prompt))
            if "Entity 8" in prompt:
                content = {
                    "summaries": [
                        {"normalized_name": "entity-8", "summary": "Entity 8 summary"}
                    ]
                }
            else:
                content = {
                    "summaries": [
                        {
                            "normalized_name": f"entity-{index}",
                            "summary": f"Entity {index} summary",
                        }
                        for index in range(8)
                    ]
                }
            return type("Resp", (), {"content": content})

    def fake_llm_factory():
        factory_calls.append("created")
        return FakeLLM()

    summary_count = asyncio.run(
        refresh_entity_summaries(
            store=FakeStore(),
            knowledge_base_id=2,
            team_id=1,
            normalized_names=[f"entity-{index}" for index in range(9)],
            llm_factory=fake_llm_factory,
        )
    )

    prompt_calls = [item for item in calls if item[0] == "prompt"]
    assert summary_count == 9
    assert len(factory_calls) == 1
    assert len(prompt_calls) == 2
    assert calls[-1][0] == "upsert"
    assert [row["summary"] for row in calls[-1][1]] == [
        f"Entity {index} summary" for index in range(9)
    ]


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
            return type(
                "Resp",
                (),
                {
                    "content": {
                        "summaries": [
                            {
                                "source_normalized_name": "projectapp",
                                "target_normalized_name": "assistantprofile",
                                "relation_type": "USES",
                                "summary": "ProjectApp 通过默认绑定使用 AssistantProfile。",
                            }
                        ]
                    }
                },
            )

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


def test_refresh_relation_summaries_batches_contexts_and_reuses_llm(monkeypatch):
    calls = []
    factory_calls = []

    contexts = [
        {
            "source_normalized_name": f"source-{index}",
            "source_display_name": f"Source {index}",
            "source_entity_type": "FEATURE",
            "source_aliases": [],
            "source_props": {},
            "target_normalized_name": f"target-{index}",
            "target_display_name": f"Target {index}",
            "target_entity_type": "FEATURE",
            "target_aliases": [],
            "target_props": {},
            "relation_type": "RELATED_TO",
            "evidence": f"Source {index} relates to Target {index}",
            "relation_props": {},
        }
        for index in range(9)
    ]

    class FakeStore:
        async def list_relation_summary_contexts(self, *, knowledge_base_id, team_id, document_id=None):
            return contexts

        async def upsert_relation_summaries(self, rows):
            calls.append(("upsert", rows))

    class FakeLLM:
        async def ainvoke(self, prompt):
            calls.append(("prompt", prompt))
            indexes = [8] if "Source 8" in prompt else list(range(8))
            return type(
                "Resp",
                (),
                {
                    "content": {
                        "summaries": [
                            {
                                "source_normalized_name": f"source-{index}",
                                "target_normalized_name": f"target-{index}",
                                "relation_type": "RELATED_TO",
                                "summary": f"Relation {index} summary",
                            }
                            for index in indexes
                        ]
                    }
                },
            )

    def fake_llm_factory():
        factory_calls.append("created")
        return FakeLLM()

    summary_count = asyncio.run(
        refresh_relation_summaries(
            store=FakeStore(),
            knowledge_base_id=2,
            team_id=1,
            document_id=9,
            llm_factory=fake_llm_factory,
        )
    )

    prompt_calls = [item for item in calls if item[0] == "prompt"]
    assert summary_count == 9
    assert len(factory_calls) == 1
    assert len(prompt_calls) == 2
    assert calls[-1][0] == "upsert"
    assert [row["summary"] for row in calls[-1][1]] == [
        f"Relation {index} summary" for index in range(9)
    ]


def test_entity_and_relation_refresh_can_share_llm_instance(monkeypatch):
    calls = []

    class FakeStore:
        async def list_entity_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names):
            return [
                {
                    "normalized_name": "projectapp",
                    "display_name": "ProjectApp",
                    "entity_type": "COMPONENT",
                    "aliases": [],
                    "entity_props": {},
                    "mentions": [{"evidence": "ProjectApp 默认绑定 AssistantProfile"}],
                    "relations": [],
                }
            ]

        async def upsert_entity_summaries(self, rows):
            calls.append(("entity-upsert", rows))

        async def list_relation_summary_contexts(self, *, knowledge_base_id, team_id, document_id=None):
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
                    "relation_props": {},
                }
            ]

        async def upsert_relation_summaries(self, rows):
            calls.append(("relation-upsert", rows))

    class SharedLLM:
        def __init__(self):
            self.prompt_count = 0

        async def ainvoke(self, prompt):
            self.prompt_count += 1
            calls.append(("llm", id(self), prompt))
            if "实体上下文列表" in prompt:
                content = {
                    "summaries": [
                        {
                            "normalized_name": "projectapp",
                            "summary": "ProjectApp 是组件。",
                        }
                    ]
                }
            else:
                content = {
                    "summaries": [
                        {
                            "source_normalized_name": "projectapp",
                            "target_normalized_name": "assistantprofile",
                            "relation_type": "USES",
                            "summary": "ProjectApp 使用 AssistantProfile。",
                        }
                    ]
                }
            return type("Resp", (), {"content": content})

    shared_llm = SharedLLM()
    store = FakeStore()

    entity_count = asyncio.run(
        refresh_entity_summaries(
            store=store,
            knowledge_base_id=2,
            team_id=1,
            normalized_names=["projectapp"],
            llm=shared_llm,
        )
    )
    relation_count = asyncio.run(
        refresh_relation_summaries(
            store=store,
            knowledge_base_id=2,
            team_id=1,
            document_id=9,
            llm=shared_llm,
        )
    )

    llm_calls = [item for item in calls if item[0] == "llm"]
    assert entity_count == 1
    assert relation_count == 1
    assert shared_llm.prompt_count == 2
    assert {item[1] for item in llm_calls} == {id(shared_llm)}
