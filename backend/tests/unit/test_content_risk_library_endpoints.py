from types import SimpleNamespace

from app.api.dependencies.auth import require_system_admin
from app.db.session import get_db
from app.main import app


def test_list_content_risk_libraries_returns_structured_items(client, monkeypatch):
    async def _fake_require_system_admin():
        return SimpleNamespace(id=1, role="system_admin")

    async def _fake_get_db():
        yield object()

    async def _fake_list_libraries(self, *, db, keyword=None, enabled=None):
        assert db is not None
        assert keyword == "作弊"
        assert enabled is True
        return [
            {
                "id": 1,
                "name": "学习诚信防作弊库",
                "description": "用于识别代写作业和直接索要答案的内容。",
                "enabled": True,
                "rule_count": 286,
                "reference_count": 1,
                "created_at": None,
                "updated_at": None,
            }
        ]

    monkeypatch.setattr(
        "app.api.v1.endpoints.content_risk_libraries.ContentRiskLibraryService.list_libraries",
        _fake_list_libraries,
    )
    app.dependency_overrides[require_system_admin] = _fake_require_system_admin
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        response = client.get(
            "/api/v1/content-risk/libraries",
            params={"keyword": "作弊", "enabled": "true"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "学习诚信防作弊库"
    assert data["items"][0]["rule_count"] == 286
    assert data["items"][0]["reference_count"] == 1


def test_list_content_risk_logs_returns_detection_logs(client, monkeypatch):
    async def _fake_require_system_admin():
        return SimpleNamespace(id=1, role="system_admin")

    async def _fake_get_db():
        yield object()

    async def _fake_list_logs(
        self,
        *,
        limit=50,
        scene=None,
        action=None,
        blocked=None,
        risk_level=None,
        chat_log_id=None,
    ):
        assert limit == 20
        assert scene == "query"
        assert action == "block"
        assert blocked is True
        assert risk_level == "high"
        assert chat_log_id == 99
        log = SimpleNamespace(
            id=5,
            chat_log_id=99,
            user_id=7,
            session_id="session-1",
            product_id=1,
            project_id=2,
            project_app_id=3,
            external_user_id="u-1",
            external_user_name="访客",
            knowledge_base_id=4,
            assistant_id=6,
            scene="query",
            action="block",
            blocked=True,
            risk_level="high",
            matched_text="加微信",
            checked_text="请加我微信",
            hits=[
                {
                    "rule_id": 12,
                    "library_id": 3,
                    "rule_name": "识别微信导流",
                    "risk_category": "广告引流",
                    "risk_level": "high",
                    "action": "block",
                    "match_mode": "contains",
                    "pattern": "加微信",
                    "matched_text": "加微信",
                }
            ],
            elapsed_ms=3,
            created_at=None,
        )
        return ([(log, "产品", "项目", "应用", "知识库", "助手")], 1)

    monkeypatch.setattr(
        "app.api.v1.endpoints.content_risk_libraries.ContentRiskLogRepository.list_logs",
        _fake_list_logs,
    )
    app.dependency_overrides[require_system_admin] = _fake_require_system_admin
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        response = client.get(
            "/api/v1/content-risk/logs",
            params={
                "limit": "20",
                "scene": "query",
                "action": "block",
                "blocked": "true",
                "risk_level": "high",
                "chat_log_id": "99",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["chat_log_id"] == 99
    assert data["items"][0]["blocked"] is True
    assert data["items"][0]["hits"][0]["rule_name"] == "识别微信导流"


def test_create_content_risk_library_returns_created_item(client, monkeypatch):
    async def _fake_require_system_admin():
        return SimpleNamespace(id=7, role="system_admin")

    async def _fake_get_db():
        yield object()

    async def _fake_create_library(self, *, db, payload, actor_user_id):
        assert db is not None
        assert actor_user_id == 7
        assert payload.name == "通用文明用语库"
        assert payload.description == "覆盖提问和回答中的不友善表达。"
        assert payload.enabled is True
        return {
            "id": 2,
            "name": payload.name,
            "description": payload.description,
            "enabled": payload.enabled,
            "rule_count": 0,
            "reference_count": 0,
            "created_at": None,
            "updated_at": None,
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.content_risk_libraries.ContentRiskLibraryService.create_library",
        _fake_create_library,
    )
    app.dependency_overrides[require_system_admin] = _fake_require_system_admin
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        response = client.post(
            "/api/v1/content-risk/libraries",
            json={
                "name": "通用文明用语库",
                "description": "覆盖提问和回答中的不友善表达。",
                "enabled": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 2
    assert data["name"] == "通用文明用语库"
    assert data["enabled"] is True


def test_update_content_risk_library_returns_updated_item(client, monkeypatch):
    async def _fake_require_system_admin():
        return SimpleNamespace(id=8, role="system_admin")

    async def _fake_get_db():
        yield object()

    async def _fake_update_library(self, library_id, *, db, payload, actor_user_id):
        assert library_id == 2
        assert db is not None
        assert actor_user_id == 8
        assert payload.name == "通用文明用语库 v2"
        assert payload.description is None
        assert payload.enabled is False
        return {
            "id": library_id,
            "name": payload.name,
            "description": payload.description,
            "enabled": payload.enabled,
            "rule_count": 12,
            "reference_count": 1,
            "created_at": None,
            "updated_at": None,
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.content_risk_libraries.ContentRiskLibraryService.update_library",
        _fake_update_library,
    )
    app.dependency_overrides[require_system_admin] = _fake_require_system_admin
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        response = client.put(
            "/api/v1/content-risk/libraries/2",
            json={
                "name": "通用文明用语库 v2",
                "description": None,
                "enabled": False,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 2
    assert data["name"] == "通用文明用语库 v2"
    assert data["enabled"] is False


def test_delete_content_risk_library_returns_no_content(client, monkeypatch):
    async def _fake_require_system_admin():
        return SimpleNamespace(id=9, role="system_admin")

    async def _fake_get_db():
        yield object()

    async def _fake_delete_library(self, library_id, *, db, actor_user_id):
        assert library_id == 2
        assert db is not None
        assert actor_user_id == 9

    monkeypatch.setattr(
        "app.api.v1.endpoints.content_risk_libraries.ContentRiskLibraryService.delete_library",
        _fake_delete_library,
    )
    app.dependency_overrides[require_system_admin] = _fake_require_system_admin
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        response = client.delete("/api/v1/content-risk/libraries/2")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""


def test_list_content_risk_rules_returns_library_rules(client, monkeypatch):
    async def _fake_require_system_admin():
        return SimpleNamespace(id=1, role="system_admin")

    async def _fake_get_db():
        yield object()

    async def _fake_list_rules(self, library_id, *, db, keyword=None, enabled=None):
        assert library_id == 3
        assert db is not None
        assert keyword == "微信"
        assert enabled is True
        return [
            {
                "id": 11,
                "library_id": library_id,
                "name": "识别微信导流",
                "description": "识别用户要求添加微信、私聊或转移到站外沟通的内容。",
                "rule_type": "keyword",
                "match_mode": "contains",
                "pattern": "加微信,加我微信,私聊,wx,微我",
                "risk_category": "广告引流",
                "risk_level": "high",
                "default_action": "block",
                "applies_to_query": True,
                "applies_to_answer": False,
                "enabled": True,
                "created_at": None,
                "updated_at": None,
            }
        ]

    monkeypatch.setattr(
        "app.api.v1.endpoints.content_risk_libraries.ContentRiskLibraryService.list_rules",
        _fake_list_rules,
    )
    app.dependency_overrides[require_system_admin] = _fake_require_system_admin
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        response = client.get(
            "/api/v1/content-risk/libraries/3/rules",
            params={"keyword": "微信", "enabled": "true"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "识别微信导流"
    assert data["items"][0]["rule_type"] == "keyword"
    assert data["items"][0]["default_action"] == "block"
    assert data["items"][0]["applies_to_query"] is True
    assert data["items"][0]["applies_to_answer"] is False


def test_create_content_risk_rule_returns_created_rule(client, monkeypatch):
    async def _fake_require_system_admin():
        return SimpleNamespace(id=7, role="system_admin")

    async def _fake_get_db():
        yield object()

    async def _fake_create_rule(self, library_id, *, db, payload, actor_user_id):
        assert library_id == 3
        assert db is not None
        assert actor_user_id == 7
        assert payload.name == "识别手机号"
        assert payload.rule_type == "regex"
        assert payload.match_mode == "regex"
        assert payload.pattern == r"1[3-9]\d{9}"
        assert payload.applies_to_query is True
        assert payload.applies_to_answer is True
        return {
            "id": 12,
            "library_id": library_id,
            "name": payload.name,
            "description": payload.description,
            "rule_type": payload.rule_type,
            "match_mode": payload.match_mode,
            "pattern": payload.pattern,
            "risk_category": payload.risk_category,
            "risk_level": payload.risk_level,
            "default_action": payload.default_action,
            "applies_to_query": payload.applies_to_query,
            "applies_to_answer": payload.applies_to_answer,
            "enabled": payload.enabled,
            "created_at": None,
            "updated_at": None,
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.content_risk_libraries.ContentRiskLibraryService.create_rule",
        _fake_create_rule,
    )
    app.dependency_overrides[require_system_admin] = _fake_require_system_admin
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        response = client.post(
            "/api/v1/content-risk/libraries/3/rules",
            json={
                "name": "识别手机号",
                "description": "识别文本中疑似手机号的内容。",
                "rule_type": "regex",
                "match_mode": "regex",
                "pattern": r"1[3-9]\d{9}",
                "risk_category": "广告引流",
                "risk_level": "high",
                "default_action": "block",
                "applies_to_query": True,
                "applies_to_answer": True,
                "enabled": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 12
    assert data["library_id"] == 3
    assert data["rule_type"] == "regex"
    assert data["applies_to_query"] is True
    assert data["applies_to_answer"] is True


def test_update_content_risk_rule_returns_updated_rule(client, monkeypatch):
    async def _fake_require_system_admin():
        return SimpleNamespace(id=8, role="system_admin")

    async def _fake_get_db():
        yield object()

    async def _fake_update_rule(self, library_id, rule_id, *, db, payload, actor_user_id):
        assert library_id == 3
        assert rule_id == 12
        assert db is not None
        assert actor_user_id == 8
        assert payload.name == "识别手机号 v2"
        assert payload.applies_to_query is False
        assert payload.applies_to_answer is True
        assert payload.enabled is False
        return {
            "id": rule_id,
            "library_id": library_id,
            "name": payload.name,
            "description": payload.description,
            "rule_type": payload.rule_type,
            "match_mode": payload.match_mode,
            "pattern": payload.pattern,
            "risk_category": payload.risk_category,
            "risk_level": payload.risk_level,
            "default_action": payload.default_action,
            "applies_to_query": payload.applies_to_query,
            "applies_to_answer": payload.applies_to_answer,
            "enabled": payload.enabled,
            "created_at": None,
            "updated_at": None,
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.content_risk_libraries.ContentRiskLibraryService.update_rule",
        _fake_update_rule,
    )
    app.dependency_overrides[require_system_admin] = _fake_require_system_admin
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        response = client.put(
            "/api/v1/content-risk/libraries/3/rules/12",
            json={
                "name": "识别手机号 v2",
                "description": None,
                "rule_type": "regex",
                "match_mode": "regex",
                "pattern": r"1[3-9]\d{9}",
                "risk_category": "广告引流",
                "risk_level": "medium",
                "default_action": "review",
                "applies_to_query": False,
                "applies_to_answer": True,
                "enabled": False,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 12
    assert data["name"] == "识别手机号 v2"
    assert data["default_action"] == "review"
    assert data["applies_to_query"] is False
    assert data["applies_to_answer"] is True
