# SynapseFlow 最小测试与混沌测试方案

## 1. 方案范围

当前项目继续使用 pytest。常规测试沿用现有 `backend/tests/unit/`，混沌测试只保留一个最小故障场景，不建设独立测试数据库、Redis、Neo4j 或 Docker 测试环境。

测试分层：

- L1：纯函数、权限规则、数据转换。
- L2：使用 Fake、`monkeypatch` 和 FastAPI `dependency_overrides` 验证业务编排与接口错误处理。
- L3：真实数据库和完整 API 链路，当前不实施。
- 混沌测试：通过故障注入模拟外部依赖异常，当前只覆盖 reranker 读取超时。

## 2. 最小混沌场景

测试文件：`backend/tests/chaos/test_reranker_timeout.py`

故障：reranker HTTP 请求发生 `httpx.ReadTimeout`。

预期：

1. 检索流程不因 reranker 超时而抛出异常；
2. 系统回退到原始候选顺序；
3. 记录包含“回退原始排序”的告警。

该测试使用 `monkeypatch` 注入超时，不访问真实网络，不需要新增依赖或启动基础设施。

## 3. 执行命令

```powershell
cd backend
uv run pytest tests/chaos/test_reranker_timeout.py -q
```

常规单元测试仍使用：

```powershell
cd backend
uv run pytest tests/unit -q
```

## 4. 当前状态

- 已有 pytest、pytest-asyncio 和 httpx 依赖；
- 已增加 reranker 超时混沌测试；
- 未建设 L3 独立测试数据库；
- 未实施 Redis、Neo4j、LLM 或对象存储故障实验；
- 后续只有出现真实需求时才扩展新的混沌场景。
