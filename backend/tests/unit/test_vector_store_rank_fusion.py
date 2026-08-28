from app.services.vector_store import reciprocal_rank_fusion_many


def test_reciprocal_rank_fusion_many_merges_multiple_rankings():
    rank_a = [
        {
            "chunk_text": "alpha",
            "document_id": 1,
            "document_chunk_id": 101,
            "chunk_index": 0,
            "distance": 0.11,
            "document_title": "Doc A",
            "metadata": {},
        },
        {
            "chunk_text": "beta",
            "document_id": 2,
            "document_chunk_id": 102,
            "chunk_index": 0,
            "distance": 0.21,
            "document_title": "Doc B",
            "metadata": {},
        },
    ]
    rank_b = [
        {
            "chunk_text": "beta",
            "document_id": 2,
            "document_chunk_id": 102,
            "chunk_index": 0,
            "distance": 0.18,
            "document_title": "Doc B",
            "metadata": {},
        },
        {
            "chunk_text": "gamma",
            "document_id": 3,
            "document_chunk_id": 103,
            "chunk_index": 0,
            "distance": 0.15,
            "document_title": "Doc C",
            "metadata": {},
        },
    ]

    fused = reciprocal_rank_fusion_many([rank_a, rank_b], rrf_k=60, limit=3)

    assert [row["document_id"] for row in fused] == [2, 1, 3]
    assert fused[0]["distance"] == 0.18
