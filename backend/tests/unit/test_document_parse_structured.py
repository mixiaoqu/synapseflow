from app.utils.document_parse import parse_raw_document_content, render_parsed_document


def test_parse_raw_markdown_content_returns_structured_blocks():
    parsed = parse_raw_document_content(
        "# Title\n\nParagraph one.\n\n- Item A\n- Item B\n\n| A | B |",
        title="Example",
        document_type="md",
    )

    assert [block.type for block in parsed.blocks] == ["heading", "paragraph", "list", "table"]
    assert parsed.blocks[0].level == 1
    assert render_parsed_document(parsed).startswith("# Title")


def test_parse_raw_text_content_normalizes_lines():
    parsed = parse_raw_document_content(
        "第一行\n第二行\n\n第三行",
        title="Plain",
        document_type="txt",
    )

    rendered = render_parsed_document(parsed)
    assert "第一行第二行" in rendered
    assert "第三行" in rendered


def test_parse_raw_markdown_content_builds_clause_tree():
    parsed = parse_raw_document_content(
        "# 用户管理\n\n"
        "1. 账号生命周期\n"
        "创建账号时需要填写姓名。\n\n"
        "1.1 创建账号\n"
        "创建后立即发送通知。\n\n"
        "1.2 删除账号\n"
        "只有超级管理员可以删除账号。",
        title="Example",
        document_type="md",
    )

    assert len(parsed.roots) == 1
    heading = parsed.roots[0]
    assert heading.node_type == "heading"
    clause = heading.children[0]
    assert clause.node_type == "clause"
    assert clause.numbering == "1"
    assert clause.text == "账号生命周期"
    assert [child.numbering for child in clause.children if child.node_type == "clause"] == ["1.1", "1.2"]


def test_parse_raw_markdown_content_builds_nested_list_tree():
    parsed = parse_raw_document_content(
        "# 权限说明\n\n"
        "- 管理员\n"
        "  - 可创建用户\n"
        "  - 可删除用户\n"
        "- 普通成员\n"
        "  - 仅可查看\n",
        title="Example",
        document_type="md",
    )

    heading = parsed.roots[0]
    list_parent = heading.children[0]
    assert list_parent.node_type == "list"
    assert [child.text for child in list_parent.children] == ["管理员", "普通成员"]
    assert [child.text for child in list_parent.children[0].children] == ["可创建用户", "可删除用户"]
