from app.agents.prompts.kb_chat import build_kb_chat_answer_prompt


def test_kb_chat_prompt_includes_assistant_layers_without_dropping_base_rules():
    prompt = build_kb_chat_answer_prompt(
        "How do I create a project?",
        "Open project settings and click the create button.",
        chat_history_text="User: How do I get started?",
        memory_summary="The user is learning the initial setup flow.",
        assistant_name="Implementation Assistant",
        assistant_welcome_message="Welcome to the implementation guide.",
        assistant_placeholder_text="Ask an implementation question",
        assistant_persona_prompt="Stay direct and professional.",
        assistant_rule_template="Use numbered steps for procedures.",
        assistant_suggested_prompts=[
            "How do I create a project?",
            "How do I configure a team?",
        ],
        evidence_status="empty",
    )

    assert "Current assistant name: Implementation Assistant" in prompt
    assert "[Assistant persona]" in prompt
    assert "Stay direct and professional." in prompt
    assert "[Configured welcome message]" in prompt
    assert "Welcome to the implementation guide." in prompt
    assert "[Configured input placeholder]" in prompt
    assert "Ask an implementation question" in prompt
    assert "[Assistant-specific response rules]" in prompt
    assert "Use numbered steps for procedures." in prompt
    assert "[Configured suggested prompts]" in prompt
    assert "- How do I create a project?" in prompt
    assert "[Evidence evaluation]" in prompt
    assert "empty" in prompt
    assert "Do not fabricate facts" in prompt
    assert "Knowledge-base context" in prompt


def test_kb_chat_prompt_keeps_readable_chinese_constraints_and_page_context_labels():
    prompt = build_kb_chat_answer_prompt(
        "如何关联子账号？",
        "在主账号详情页点击添加账号关联。",
        page_config={
            "page_name": "账号详情",
            "page_description": "用于查看和维护账号资料",
            "assistant_intro": "可咨询账号相关问题",
        },
        page_context={"page_type": "account-detail"},
        evidence_status="sufficient",
    )

    assert "资料中没有提到" in prompt
    assert "根据现有资料无法确定" in prompt
    assert "页面名称：账号详情" in prompt
    assert "页面标识：account-detail" in prompt
    assert "页面说明：用于查看和维护账号资料" in prompt
    assert "助手入口说明：可咨询账号相关问题" in prompt
    assert "以上信息描述用户提问时所在的业务环境" in prompt
    assert "按内容选择清晰的排版" in prompt
