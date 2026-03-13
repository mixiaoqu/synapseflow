"use client";

import { useState } from "react";

export default function QAPage() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await fetch("http://localhost:8000/api/v1/qa/invoke", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, max_iterations: 3 }),
      });
      
      const data = await response.json();
      setAnswer(data.answer);
    } catch (error) {
      console.error("Error:", error);
      setAnswer("发生错误，请重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="container mx-auto px-4 max-w-4xl">
        <h1 className="text-4xl font-bold mb-8">迭代问答</h1>
        
        <div className="bg-white rounded-lg shadow-lg p-8">
          <form onSubmit={handleSubmit} className="mb-8">
            <label className="block text-sm font-medium mb-2">
              输入您的问题：
            </label>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full p-4 border rounded-lg mb-4 min-h-[100px]"
              placeholder="例如：什么是LangGraph？"
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "处理中..." : "提问"}
            </button>
          </form>

          {answer && (
            <div className="border-t pt-8">
              <h3 className="text-lg font-semibold mb-4">答案：</h3>
              <div className="prose max-w-none">
                <p className="whitespace-pre-wrap">{answer}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
