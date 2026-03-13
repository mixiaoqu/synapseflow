"use client";

import { useState } from "react";

export default function RevisionPage() {
  const [document, setDocument] = useState("");
  const [revisedDoc, setRevisedDoc] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await fetch("http://localhost:8000/api/v1/revision/invoke", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document, max_iterations: 5 }),
      });
      
      const data = await response.json();
      setRevisedDoc(data.revised_document);
    } catch (error) {
      console.error("Error:", error);
      setRevisedDoc("发生错误，请重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="container mx-auto px-4 max-w-6xl">
        <h1 className="text-4xl font-bold mb-8">递归修订</h1>
        
        <div className="grid md:grid-cols-2 gap-8">
          <div className="bg-white rounded-lg shadow-lg p-8">
            <h2 className="text-2xl font-semibold mb-4">原始文档</h2>
            <form onSubmit={handleSubmit}>
              <textarea
                value={document}
                onChange={(e) => setDocument(e.target.value)}
                className="w-full p-4 border rounded-lg mb-4 min-h-[400px] font-mono text-sm"
                placeholder="粘贴需要修订的文档..."
              />
              <button
                type="submit"
                disabled={loading || !document.trim()}
                className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? "修订中..." : "开始修订"}
              </button>
            </form>
          </div>

          <div className="bg-white rounded-lg shadow-lg p-8">
            <h2 className="text-2xl font-semibold mb-4">修订后文档</h2>
            {revisedDoc ? (
              <div className="prose max-w-none">
                <pre className="whitespace-pre-wrap text-sm">{revisedDoc}</pre>
              </div>
            ) : (
              <p className="text-gray-400">修订结果将显示在这里...</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
