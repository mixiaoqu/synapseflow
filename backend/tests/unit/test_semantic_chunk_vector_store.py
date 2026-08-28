import asyncio

from app.core.config.schemas import RagChunkConfig, RagConfig, RagRetrievalConfig
from app.services.semantic_chunk import (
    CHUNKING_VERSION,
    build_chunk_plan,
    build_vector_index_chunks,
)
from app.services.vector_store import add_document_chunks
from app.utils.document_parse import ParsedBlock, ParsedDocument, parse_raw_document_content


class _DummyDB:
    def __init__(self) -> None:
        self.rows = []
        self.commits = 0

    def add_all(self, rows) -> None:
        self.rows.extend(rows)

    async def commit(self) -> None:
        self.commits += 1


def _rag_config(
    *,
    child_target_max: int = 900,
    split_overlap_units: int = 1,
) -> RagConfig:
    return RagConfig(
        chunk=RagChunkConfig(
            size=700,
            overlap=100,
            parent_target_min=1200,
            parent_target_max=2500,
            child_target_min=400,
            child_target_max=child_target_max,
            split_overlap_units=split_overlap_units,
            parent_window_max_chars=1800,
            parent_window_neighbor_span=1,
        ),
        retrieval=RagRetrievalConfig(
            k_first=32,
            distance_threshold=0.5,
            rrf_score_threshold=None,
            rerank_threshold=None,
            final_top_k=12,
            llm_reference_top_k=8,
            hybrid_enabled=True,
            lexical_k=32,
            rrf_k=60,
            hybrid_pool_limit=64,
            kb_context_max_chars=12000,
            profiles={},
        ),
    )


def test_build_chunk_plan_creates_parent_child_hierarchy():
    parsed = ParsedDocument(
        title="System Design Notes",
        blocks=[
            ParsedBlock(type="heading", text="Parent", level=1),
            ParsedBlock(type="paragraph", text="A" * 1400),
            ParsedBlock(type="heading", text="Child", level=2),
            ParsedBlock(type="paragraph", text="B" * 700),
            ParsedBlock(type="list", text="- item 1\n- item 2"),
        ],
    )

    plan = build_chunk_plan(parsed, document_title=parsed.title)

    assert plan.full_text.startswith("# Parent")
    assert len(plan.parent_chunks) >= 1
    assert len(plan.child_chunks) >= 2
    assert all(chunk.parent_local_id is not None for chunk in plan.child_chunks)
    assert plan.child_chunks[0].next_local_id == plan.child_chunks[1].local_id
    assert plan.child_chunks[1].prev_local_id == plan.child_chunks[0].local_id
    assert any(chunk.section_path == "Parent > Child" for chunk in plan.child_chunks)


def test_build_chunk_plan_honors_configured_child_target_max(monkeypatch):
    monkeypatch.setattr(
        "app.services.semantic_chunk.config_registry.get_rag_config",
        lambda: _rag_config(child_target_max=220, split_overlap_units=0),
    )
    parsed = ParsedDocument(
        title="Chunk Boundaries",
        blocks=[
            ParsedBlock(type="heading", text="Policy", level=1),
            ParsedBlock(type="paragraph", text=("A" * 180) + "\n" + ("B" * 180) + "\n" + ("C" * 180)),
        ],
    )

    plan = build_chunk_plan(parsed, document_title=parsed.title)

    assert len(plan.child_chunks) >= 3


def test_build_chunk_plan_splits_oversized_tree_leaf_without_losing_content(monkeypatch):
    monkeypatch.setattr(
        "app.services.semantic_chunk.config_registry.get_rag_config",
        lambda: _rag_config(child_target_max=80, split_overlap_units=0),
    )
    body = "第一段说明。" * 12 + "\n\n" + "第二段结论。" * 12
    parsed = parse_raw_document_content(
        f"# 超长章节\n\n{body}",
        title="操作手册",
        document_type="md",
    )

    plan = build_chunk_plan(parsed, document_title=parsed.title)

    assert len(plan.child_chunks) > 1
    assert all(len(chunk.content) <= 80 for chunk in plan.child_chunks)
    assert "第一段说明。" in "".join(chunk.content for chunk in plan.child_chunks)
    assert "第二段结论。" in "".join(chunk.content for chunk in plan.child_chunks)
    parent_content = "\n\n".join(chunk.content for chunk in plan.parent_chunks)
    assert parent_content.count("第一段说明。") == 12
    assert parent_content.count("第二段结论。") == 12
    assert all("超长章节" in chunk.search_text for chunk in plan.child_chunks)
    for parent in plan.parent_chunks:
        children = [chunk for chunk in plan.child_chunks if chunk.parent_local_id == parent.local_id]
        child_unit_indexes = {chunk.metadata["child_index_within_parent"] for chunk in children}
        for child_unit_index in child_unit_indexes:
            segments = [
                chunk
                for chunk in children
                if chunk.metadata["child_index_within_parent"] == child_unit_index
            ]
            assert all(chunk.metadata["segment_count"] == len(segments) for chunk in segments)


def test_build_chunk_plan_adds_stable_chunk_identity_metadata():
    parsed = ParsedDocument(
        title="Identity",
        blocks=[ParsedBlock(type="paragraph", text="Stable chunk content")],
    )

    first = build_chunk_plan(parsed, document_title=parsed.title)
    second = build_chunk_plan(parsed, document_title=parsed.title)

    assert first.child_chunks[0].metadata["chunking_version"] == CHUNKING_VERSION
    assert first.child_chunks[0].metadata["content_fingerprint"] == second.child_chunks[0].metadata[
        "content_fingerprint"
    ]


def test_add_document_chunks_stores_document_chunk_relationships():
    parsed = ParsedDocument(
        title="System Design Notes",
        blocks=[
            ParsedBlock(type="heading", text="Parent", level=1),
            ParsedBlock(type="paragraph", text="Rendered body " * 40),
        ],
    )
    plan = build_chunk_plan(parsed, document_title=parsed.title)
    vector_chunks = build_vector_index_chunks(plan, document_id=7)
    document_chunk_ids = [101 + index for index, _ in enumerate(vector_chunks)]
    db = _DummyDB()

    count = asyncio.run(
        add_document_chunks(
            db,
            7,
            vector_chunks,
            [[0.1, 0.2] for _ in vector_chunks],
            document_chunk_ids=document_chunk_ids,
            commit=False,
        )
    )

    assert count == len(vector_chunks)
    assert len(db.rows) == len(vector_chunks)
    row = db.rows[0]
    assert row.document_id == 7
    assert row.document_chunk_id == document_chunk_ids[0]
    assert row.chunk_index == vector_chunks[0].metadata["chunk_index"]
    assert row.metadata_["document_chunk_id"] == document_chunk_ids[0]


def test_add_document_chunks_rejects_mismatched_document_chunk_ids():
    parsed = ParsedDocument(
        title="System Design Notes",
        blocks=[
            ParsedBlock(type="heading", text="Parent", level=1),
            ParsedBlock(type="paragraph", text="Rendered body " * 40),
        ],
    )
    plan = build_chunk_plan(parsed, document_title=parsed.title)
    vector_chunks = build_vector_index_chunks(plan, document_id=7)
    db = _DummyDB()

    try:
        asyncio.run(
            add_document_chunks(
                db,
                7,
                vector_chunks,
                [[0.1, 0.2] for _ in vector_chunks],
                document_chunk_ids=[],
                commit=False,
            )
        )
    except ValueError as exc:
        assert "document_chunk_ids" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected add_document_chunks to reject mismatched ids")


def test_build_chunk_plan_keeps_clause_subtree_together():
    parsed = parse_raw_document_content(
        "# 用户管理\n\n"
        "1. 账号生命周期\n"
        "创建账号时需要填写姓名。\n\n"
        "1.1 创建账号\n"
        "创建后立即发送通知。\n\n"
        "1.2 删除账号\n"
        "只有超级管理员可以删除账号。",
        title="用户管理",
        document_type="md",
    )

    plan = build_chunk_plan(parsed, document_title=parsed.title)

    assert any("1. 账号生命周期" in chunk.content and "1.1 创建账号" in chunk.content for chunk in plan.parent_chunks)
    assert any(
        chunk.metadata.get("node_type") == "clause" and chunk.metadata.get("numbering") == "1.1"
        for chunk in plan.child_chunks
    )
    assert any(
        chunk.metadata.get("node_type") == "clause" and chunk.metadata.get("numbering") == "1.2"
        for chunk in plan.child_chunks
    )
    child_contents = {
        chunk.metadata.get("numbering"): chunk.content
        for chunk in plan.child_chunks
        if chunk.metadata.get("node_type") == "clause"
    }
    assert "1. 账号生命周期" not in child_contents["1.1"]
    assert child_contents["1.1"].startswith("1.1 创建账号")
    assert "1. 账号生命周期" not in child_contents["1.2"]


def test_build_chunk_plan_resolves_tree_chunk_offsets_from_full_text():
    parsed = parse_raw_document_content(
        "# 用户管理\n\n"
        "1. 账号生命周期\n"
        "创建账号时需要填写姓名。\n\n"
        "1.1 创建账号\n"
        "创建后立即发送通知。\n\n"
        "1.2 删除账号\n"
        "只有超级管理员可以删除账号。",
        title="用户管理",
        document_type="md",
    )

    plan = build_chunk_plan(parsed, document_title=parsed.title)

    delete_chunk = next(
        chunk
        for chunk in plan.child_chunks
        if chunk.metadata.get("node_type") == "clause" and chunk.metadata.get("numbering") == "1.2"
    )
    expected_start = plan.full_text.index("1.2 删除账号")
    assert delete_chunk.start_offset == expected_start
    assert delete_chunk.end_offset == expected_start + len(delete_chunk.content)
    assert plan.full_text[delete_chunk.start_offset : delete_chunk.end_offset] == delete_chunk.content


def test_build_chunk_plan_uses_heading_section_as_parent_and_merges_qa_child():
    parsed = parse_raw_document_content(
        "## 常见问题\n\n"
        "**Q12：为什么保存时没有提示必填字段为空？**\n\n"
        "A：当前编辑子页面的表单校验规则已在代码中定义但未绑定到表单组件，"
        "保存方法中的手动校验逻辑也已被注释掉，因此前端不会拦截空字段提交。",
        title="常见问题",
        document_type="md",
    )

    plan = build_chunk_plan(parsed, document_title=parsed.title)

    section_parent = next(chunk for chunk in plan.parent_chunks if chunk.metadata.get("node_type") == "heading")
    assert section_parent.content.startswith("## 常见问题")
    assert "Q12：为什么保存时没有提示必填字段为空？" in section_parent.content
    assert "A：当前编辑子页面的表单校验规则" in section_parent.content

    assert len(plan.child_chunks) == 1
    qa_child = plan.child_chunks[0]
    assert qa_child.parent_local_id == section_parent.local_id
    assert qa_child.metadata.get("node_type") == "qa_pair"
    assert "Q12：为什么保存时没有提示必填字段为空？" in qa_child.content
    assert "A：当前编辑子页面的表单校验规则" in qa_child.content


def test_build_chunk_plan_keeps_short_list_as_one_child_under_heading_parent():
    parsed = parse_raw_document_content(
        "## 显示逻辑说明\n\n"
        "- 折扣权益、专属商品权益、折上折权益：仅可配置PLUS权益名称和内容\n"
        "- 赠送积分：仅可配置普通会员权益\n"
        "- 其他类型（含自定义权益）：所有四个字段均可配置\n",
        title="显示逻辑说明",
        document_type="md",
    )

    plan = build_chunk_plan(parsed, document_title=parsed.title)

    assert len(plan.parent_chunks) == 1
    assert plan.parent_chunks[0].metadata.get("node_type") == "heading"
    assert len(plan.child_chunks) == 1
    assert plan.child_chunks[0].metadata.get("node_type") == "list"
    assert "折扣权益" in plan.child_chunks[0].content
    assert "赠送积分" in plan.child_chunks[0].content
    assert "其他类型" in plan.child_chunks[0].content


def test_build_chunk_plan_merges_short_bold_intro_with_following_short_list():
    parsed = parse_raw_document_content(
        "## 相关资源\n\n"
        "**3. 查看牌照**\n\n"
        '- 点击"查看牌照"按钮\n'
        "- 查看各类经营牌照\n"
        "- 可新增、编辑或删除牌照\n",
        title="相关资源",
        document_type="md",
    )

    plan = build_chunk_plan(parsed, document_title=parsed.title)

    assert len(plan.parent_chunks) == 1
    assert plan.parent_chunks[0].metadata.get("node_type") == "heading"
    assert len(plan.child_chunks) == 1
    assert plan.child_chunks[0].metadata.get("node_type") == "semantic_group"
    assert "**3. 查看牌照**" in plan.child_chunks[0].content
    assert '点击"查看牌照"按钮' in plan.child_chunks[0].content
    assert "查看各类经营牌照" in plan.child_chunks[0].content
    assert "可新增、编辑或删除牌照" in plan.child_chunks[0].content


def test_build_chunk_plan_merges_short_intro_with_following_compact_clauses():
    parsed = parse_raw_document_content(
        "### 2.2 页面布局\n\n"
        "页面分为三个区域：\n\n"
        "1. **筛选区**（顶部）：用于快速查找采购商\n"
        "2. **列表区**（中间）：显示符合条件的采购商列表\n"
        "3. **操作区**（每条记录右侧）：提供具体操作按钮\n",
        title="页面布局",
        document_type="md",
    )

    plan = build_chunk_plan(parsed, document_title=parsed.title)

    assert len(plan.parent_chunks) == 1
    assert plan.parent_chunks[0].metadata.get("node_type") == "heading"
    assert len(plan.child_chunks) == 1
    assert plan.child_chunks[0].metadata.get("node_type") == "semantic_group"
    assert "页面分为三个区域：" in plan.child_chunks[0].content
    assert "**筛选区**" in plan.child_chunks[0].content
    assert "**列表区**" in plan.child_chunks[0].content
    assert "**操作区**" in plan.child_chunks[0].content


def test_build_chunk_plan_keeps_list_parent_and_children_together():
    parsed = parse_raw_document_content(
        "# 权限说明\n\n"
        "- 管理员\n"
        "  - 可创建用户\n"
        "  - 可删除用户\n"
        "- 普通成员\n"
        "  - 仅可查看\n",
        title="权限说明",
        document_type="md",
    )

    plan = build_chunk_plan(parsed, document_title=parsed.title)

    assert any("管理员" in chunk.content and "可删除用户" in chunk.content for chunk in plan.parent_chunks)
    assert any(chunk.metadata.get("node_type") == "list" for chunk in plan.child_chunks)


def test_build_chunk_plan_repeats_table_header_for_row_chunks(monkeypatch):
    monkeypatch.setattr(
        "app.services.semantic_chunk.config_registry.get_rag_config",
        lambda: _rag_config(child_target_max=50, split_overlap_units=0),
    )
    parsed = parse_raw_document_content(
        "# 角色权限\n\n"
        "| 角色 | 权限 | 备注 |\n"
        "| --- | --- | --- |\n"
        "| 管理员 | 创建、删除 | 默认启用 |\n"
        "| 普通成员 | 查看 | 不可删除 |\n",
        title="角色权限",
        document_type="md",
    )

    plan = build_chunk_plan(parsed, document_title=parsed.title)

    table_children = [
        chunk for chunk in plan.child_chunks if chunk.metadata.get("node_type") == "table_row_group"
    ]
    assert len(table_children) >= 2
    assert all("角色 | 权限 | 备注" in chunk.content for chunk in table_children)


def test_build_chunk_plan_groups_multiple_table_rows_when_budget_allows(monkeypatch):
    monkeypatch.setattr(
        "app.services.semantic_chunk.config_registry.get_rag_config",
        lambda: _rag_config(child_target_max=160, split_overlap_units=0),
    )
    parsed = parse_raw_document_content(
        "# 角色权限\n\n"
        "| 角色 | 权限 | 备注 |\n"
        "| --- | --- | --- |\n"
        "| 管理员 | 创建、删除 | 默认启用 |\n"
        "| 普通成员 | 查看 | 不可删除 |\n"
        "| 访客 | 查看首页 | 只读 |\n",
        title="角色权限",
        document_type="md",
    )

    plan = build_chunk_plan(parsed, document_title=parsed.title)

    table_children = [
        chunk for chunk in plan.child_chunks if chunk.metadata.get("node_type") in {"table", "table_row_group"}
    ]
    assert len(table_children) == 1
    assert "管理员" in table_children[0].content
    assert "普通成员" in table_children[0].content
    assert "访客" in table_children[0].content
