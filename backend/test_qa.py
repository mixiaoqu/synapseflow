"""临时测试脚本：调用知识库治理问答 API。"""

import asyncio

import httpx


async def test_qa_invoke():
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "http://127.0.0.1:8000/api/v1/kb-curation/invoke",
            json={"query": "什么是 LangGraph？", "max_iterations": 3},
        )
        print("Status:", resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            print("Response keys:", list(data.keys()))
            print("Answer:", (data.get("answer") or "")[:200], "...")
            print("Confidence:", data.get("confidence_score"))
            print("Iteration:", data.get("iteration"))
            hist = data.get("iteration_history") or data.get("iterationHistory") or []
            print("Iteration History:", len(hist), "rounds")
            for i, record in enumerate(hist, 1):
                print(
                    f"  Round {i}: score={record.get('score')}, "
                    f"passed={record.get('passed')}, "
                    f"q={record.get('question', '')[:50]}..."
                )
        else:
            print("Error:", resp.text[:500])


if __name__ == "__main__":
    asyncio.run(test_qa_invoke())
