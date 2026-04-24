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
