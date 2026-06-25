import asyncio

from app.services.graph_entity_candidate_service import resolve_graph_candidate_entities


class FakeEntityLookupStore:
    def __init__(self, rows_by_candidate: dict[str, list[dict]]):
        self.rows_by_candidate = rows_by_candidate

    async def lookup_entities_for_grounding(self, *, knowledge_base_id, team_id, candidate):
        assert knowledge_base_id == 1
        assert team_id == 1
        return list(self.rows_by_candidate.get(candidate, []))


def test_resolve_graph_candidates_prefers_name_over_alias():
    store = FakeEntityLookupStore(
        rows_by_candidate={
            "payment": [
                {
                    "entity_id": "entity-payment",
                    "name": "Payment",
                    "entity_type": "MODULE",
                    "aliases": ["支付模块"],
                },
                {
                    "entity_id": "entity-payment-status",
                    "name": "PaymentStatus",
                    "entity_type": "STATUS",
                    "aliases": ["payment"],
                },
            ]
        }
    )

    result = asyncio.run(
        resolve_graph_candidate_entities(
            candidate_entities=["payment"],
            query="payment",
            knowledge_base_id=1,
            team_id=1,
            store=store,
        )
    )

    assert result["candidate_entities"][0] == "Payment"
    assert result["matched_entities"][0]["entity_id"] == "entity-payment"
    assert result["matched_entities"][0]["match_type"] == "name_exact"


def test_resolve_graph_candidates_does_not_use_lexical_terms_when_candidate_exists():
    store = FakeEntityLookupStore(
        rows_by_candidate={
            "函数": [
                {
                    "entity_id": "entity-unrelated-function",
                    "name": "getGoodNum",
                    "entity_type": "FUNCTION",
                    "canonical_name": "bin/orderPay.js::getGoodNum",
                    "aliases": [],
                    "description": "函数定义",
                }
            ],
            "文件": [
                {
                    "entity_id": "entity-unrelated-file",
                    "name": "addAppVersion.js",
                    "entity_type": "FILE",
                    "canonical_name": "bin/addAppVersion.js",
                    "aliases": [],
                    "description": "文件声明",
                }
            ],
        }
    )

    result = asyncio.run(
        resolve_graph_candidate_entities(
            candidate_entities=["yunzhonghe"],
            lexical_terms=["yunzhonghe", "函数", "方法", "文件"],
            query="yunzhonghe 文件中包含哪些函数和方法",
            knowledge_base_id=1,
            team_id=1,
            store=store,
        )
    )

    assert result["candidate_entities"] == ["yunzhonghe"]
    assert result["matched_entities"] == []
    assert result["trace"]["fallback_used"] is True
