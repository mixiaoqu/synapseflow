from app.agents.prompts.kb_chat import build_kb_chat_answer_prompt


def test_kb_chat_prompt_includes_layered_evidence_and_core_rules():
    prompt = build_kb_chat_answer_prompt(
        query="How do I create a project?",
        chat_history_text="User: How do I get started?",
        memory_summary="The user is learning the initial setup flow.",
        assistant_name="Implementation Assistant",
        assistant_persona_prompt="Stay direct and professional.",
        assistant_rule_template="Use numbered steps for procedures.",
        page_context="页面名称：项目设置",
        evidence_status="empty",
        primary_context="Open project settings and click the create button.",
        supporting_context="The create button is available only after selecting a workspace.",
    )

    assert "Current assistant name: Implementation Assistant" in prompt
    assert "[Assistant persona]" in prompt
    assert "Stay direct and professional." in prompt
    assert "[Assistant-specific response rules]" in prompt
    assert "Use numbered steps for procedures." in prompt
    assert "[Evidence evaluation]" in prompt
    assert "empty" in prompt
    assert "Answer only from the provided evidence." in prompt
    assert "[Primary evidence]" in prompt
    assert "Open project settings and click the create button." in prompt
    assert "[Supporting evidence]" in prompt
    assert "available only after selecting a workspace" in prompt
    assert "[Configured welcome message]" not in prompt
    assert "[Configured input placeholder]" not in prompt
    assert "[Configured suggested prompts]" not in prompt


def test_kb_chat_prompt_keeps_readable_chinese_constraints_and_page_context_labels():
    prompt = build_kb_chat_answer_prompt(
        query="如何关联子账号？",
        page_context="\n".join(
            [
                "页面名称：账号详情",
                "页面标识：account-detail",
                "页面说明：用于查看和维护账号资料",
                "助手入口说明：可咨询账号相关问题",
            ]
        ),
        evidence_status="sufficient",
        primary_context="在主账号详情页点击添加账号关联。",
    )

    assert "资料中未直接说明" in prompt
    assert "根据现有资料无法确定" in prompt
    assert "页面名称：账号详情" in prompt
    assert "页面标识：account-detail" in prompt
    assert "页面说明：用于查看和维护账号资料" in prompt
    assert "助手入口说明：可咨询账号相关问题" in prompt
    assert "do not use it alone to answer “作用 / 用途 / 流程 / 影响 / 规则” questions" in prompt
    assert "Use clear Chinese formatting appropriate to the content." in prompt


def test_kb_chat_answer_prompt_preserves_business_routes():
    context = "请进入处方列表（prescription/list）审核待处理处方。"

    prompt = build_kb_chat_answer_prompt("在哪里审核处方单", primary_context=context)

    assert context in prompt
