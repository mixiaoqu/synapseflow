"""Temporary smoke script for the active `/api/v1/ask/invoke` endpoint."""

from __future__ import annotations

import asyncio
import os

import httpx


API_BASE_URL = os.getenv("SYNAPSEFLOW_API_BASE_URL", "http://127.0.0.1:8000")
API_TOKEN = os.getenv("SYNAPSEFLOW_API_TOKEN", "")
TEAM_ID = int(os.getenv("SYNAPSEFLOW_TEAM_ID", "0"))
KNOWLEDGE_BASE_ID = int(os.getenv("SYNAPSEFLOW_KB_ID", "0"))


async def test_ask_invoke() -> None:
    if not API_TOKEN:
        raise RuntimeError("Set SYNAPSEFLOW_API_TOKEN before running this script.")
    if TEAM_ID <= 0:
        raise RuntimeError("Set SYNAPSEFLOW_TEAM_ID before running this script.")

    payload = {
        "query": "什么是 LangGraph？",
        "team_id": TEAM_ID,
    }
    if KNOWLEDGE_BASE_ID > 0:
        payload["knowledge_base_id"] = KNOWLEDGE_BASE_ID

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{API_BASE_URL}/api/v1/ask/invoke",
            json=payload,
            headers=headers,
        )

    print("Status:", response.status_code)
    if response.status_code != 200:
        print("Error:", response.text[:1000])
        return

    data = response.json()
    print("Response keys:", list(data.keys()))
    print("Session ID:", data.get("session_id"))
    print("Log ID:", data.get("log_id"))
    print("Answer preview:", (data.get("answer_text") or "")[:300], "...")
    print("Answer status:", data.get("answer_status"))
    print("Citations:", len(data.get("backend_citations") or []))


if __name__ == "__main__":
    asyncio.run(test_ask_invoke())
