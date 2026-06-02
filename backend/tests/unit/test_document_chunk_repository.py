from types import SimpleNamespace

from app.repositories.document_chunk_repository import _resolve_parent_window_expansion


def test_resolve_parent_window_expansion_prefers_structured_focus_over_neighbors():
    parent_row = SimpleNamespace(
        id=100,
        content="1. 账号生命周期\n\n1.1 创建账号\n内容一\n\n1.2 删除账号\n内容二\n\n1.3 冻结账号\n内容三",
        metadata_={"node_type": "clause", "tree_path": ["用户管理", "1. 账号生命周期"]},
    )
    hit_row = SimpleNamespace(
        id=12,
        content="1.2 删除账号\n\n只有超级管理员可以删除账号。",
        metadata_={"node_type": "clause", "tree_path": ["用户管理", "1. 账号生命周期", "1.2 删除账号"]},
    )
    sibling_before = SimpleNamespace(
        id=11,
        content="1.1 创建账号\n\n创建后立即发送通知。",
        metadata_={"node_type": "clause", "tree_path": ["用户管理", "1. 账号生命周期", "1.1 创建账号"]},
    )
    sibling_after = SimpleNamespace(
        id=13,
        content="1.3 冻结账号\n\n冻结后不可登录。",
        metadata_={"node_type": "clause", "tree_path": ["用户管理", "1. 账号生命周期", "1.3 冻结账号"]},
    )

    expansion = _resolve_parent_window_expansion(
        row=hit_row,
        parent_row=parent_row,
        siblings=[sibling_before, hit_row, sibling_after],
        target_ids=[12],
        resolved_max_parent_chars=30,
        resolved_neighbor_span=1,
    )

    assert expansion["expansion_mode"] == "structured_focus"
    assert expansion["window_child_ids"] == [12]
    assert "1. 账号生命周期" in str(expansion["content"])
    assert "1.2 删除账号" in str(expansion["content"])
    assert "1.1 创建账号" not in str(expansion["content"])
    assert "1.3 冻结账号" not in str(expansion["content"])


def test_resolve_parent_window_expansion_keeps_neighbor_window_for_non_structured_parent():
    parent_row = SimpleNamespace(
        id=200,
        content="普通段落父块内容过长无法整体返回",
        metadata_={"node_type": "paragraph", "tree_path": ["说明"]},
    )
    sibling_before = SimpleNamespace(id=21, content="前一段", metadata_={"node_type": "paragraph"})
    hit_row = SimpleNamespace(id=22, content="命中段", metadata_={"node_type": "paragraph"})
    sibling_after = SimpleNamespace(id=23, content="后一段", metadata_={"node_type": "paragraph"})

    expansion = _resolve_parent_window_expansion(
        row=hit_row,
        parent_row=parent_row,
        siblings=[sibling_before, hit_row, sibling_after],
        target_ids=[22],
        resolved_max_parent_chars=8,
        resolved_neighbor_span=1,
    )

    assert expansion["expansion_mode"] == "window"
    assert expansion["window_child_ids"] == [21, 22, 23]
    assert "前一段" in str(expansion["content"])
    assert "命中段" in str(expansion["content"])
    assert "后一段" in str(expansion["content"])
