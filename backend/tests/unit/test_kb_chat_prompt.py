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
        retrieval_status="no_hits",
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
    assert "[Retrieval status]" in prompt
    assert "no_hits" in prompt
    assert "Do not fabricate facts" in prompt
    assert "Knowledge-base context" in prompt
