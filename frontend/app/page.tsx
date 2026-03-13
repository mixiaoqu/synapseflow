import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      <div className="container mx-auto px-4 py-16">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            SynapseFlow
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            基于LangGraph的智能体协同系统
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {/* 场景1：迭代问答 */}
          <Link href="/qa">
            <div className="bg-white rounded-lg shadow-lg p-8 hover:shadow-xl transition-shadow cursor-pointer border-2 border-transparent hover:border-blue-500">
              <div className="text-4xl mb-4">💬</div>
              <h2 className="text-2xl font-semibold mb-3 text-gray-900">
                迭代问答
              </h2>
              <p className="text-gray-600 mb-4">
                多轮知识库问答，自动优化答案质量
              </p>
              <div className="text-blue-600 font-medium">
                开始使用 →
              </div>
            </div>
          </Link>

          {/* 场景2：递归修订 */}
          <Link href="/revision">
            <div className="bg-white rounded-lg shadow-lg p-8 hover:shadow-xl transition-shadow cursor-pointer border-2 border-transparent hover:border-blue-500">
              <div className="text-4xl mb-4">📝</div>
              <h2 className="text-2xl font-semibold mb-3 text-gray-900">
                递归修订
              </h2>
              <p className="text-gray-600 mb-4">
                自动检测文档遗漏，智能补充完善
              </p>
              <div className="text-blue-600 font-medium">
                开始使用 →
              </div>
            </div>
          </Link>

          {/* 场景3：文档转原型 */}
          <Link href="/prototype">
            <div className="bg-white rounded-lg shadow-lg p-8 hover:shadow-xl transition-shadow cursor-pointer border-2 border-transparent hover:border-blue-500">
              <div className="text-4xl mb-4">🎨</div>
              <h2 className="text-2xl font-semibold mb-3 text-gray-900">
                文档转原型
              </h2>
              <p className="text-gray-600 mb-4">
                需求文档自动生成可交互的HTML原型
              </p>
              <div className="text-blue-600 font-medium">
                开始使用 →
              </div>
            </div>
          </Link>
        </div>
      </div>
    </div>
  );
}
