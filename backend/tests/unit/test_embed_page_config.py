from app.core.config.embed_pages import _load_embed_page_config_data, get_embed_page_config


def test_embed_page_config_uses_product_project_app_path(monkeypatch):
    calls = []

    def fake_load(product_code: str, project_code: str, app_code: str):
        calls.append((product_code, project_code, app_code))
        return {
            "pages": {
                "backgroundHome": {
                    "page_name": "后台首页",
                    "page_description": "后台首页说明",
                    "assistant_intro": "你正在后台首页。",
                    "suggested_questions": ["问题1", "问题2"],
                }
            }
        }

    monkeypatch.setattr("app.core.config.embed_pages.load_embed_app_pages_raw", fake_load)
    _load_embed_page_config_data.cache_clear()

    try:
        config = get_embed_page_config("b2b", "b2b演示版", "background", "backgroundHome")
        assert config is not None
        assert config.page_name == "后台首页"
        assert calls == [("b2b", "b2b演示版", "background")]
    finally:
        _load_embed_page_config_data.cache_clear()
