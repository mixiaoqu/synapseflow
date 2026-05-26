import asyncio

from app.services.kb_entity_grounding import ground_graph_entities


class FakeEntityLookupStore:
    def __init__(self, rows_by_candidate: dict[str, list[dict]]):
        self.rows_by_candidate = rows_by_candidate

    async def lookup_entities_for_grounding(self, *, knowledge_base_id, team_id, candidate):
        assert knowledge_base_id == 1
        assert team_id == 1
        return list(self.rows_by_candidate.get(candidate, []))


def test_ground_entities_prefers_normalized_name_over_alias():
    store = FakeEntityLookupStore(
        rows_by_candidate={
            "payment": [
                {
                    "normalized_name": "payment",
                    "display_name": "Payment",
                    "entity_type": "MODULE",
                    "aliases": ["支付模块"],
                },
                {
                    "normalized_name": "payment_status",
                    "display_name": "PaymentStatus",
                    "entity_type": "STATUS",
                    "aliases": ["payment"],
                },
            ]
        }
    )

    result = asyncio.run(
        ground_graph_entities(
            candidate_entities=["payment"],
            knowledge_base_id=1,
            team_id=1,
            store=store,
        )
    )

    assert result["grounded_entities"][0]["normalized_name"] == "payment"
    assert result["grounded_entities"][0]["match_type"] == "normalized_name_exact"

