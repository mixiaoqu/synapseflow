import Link from "next/link";

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      <div className="container mx-auto px-4 py-16">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            SynapseFlow
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            选择一个智能体场景开始
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          <Link href="/qa">
            <div className="bg-white rounded-lg shadow-lg p-8 hover:shadow-xl transition-shadow cursor-pointer">
              <div className="text-4xl mb-4">💬</div>
              <h2 className="text-2xl font-semibold mb-3">迭代问答</h2>
              <p className="text-gray-600">多轮知识库问答</p>
            </div>
          </Link>

          <Link href="/revision">
            <div className="bg-white rounded-lg shadow-lg p-8 hover:shadow-xl transition-shadow cursor-pointer">
              <div className="text-4xl mb-4">📝</div>
              <h2 className="text-2xl font-semibold mb-3">递归修订</h2>
              <p className="text-gray-600">文档智能补充</p>
            </div>
          </Link>

          <Link href="/prototype">
            <div className="bg-white rounded-lg shadow-lg p-8 hover:shadow-xl transition-shadow cursor-pointer">
              <div className="text-4xl mb-4">🎨</div>
              <h2 className="text-2xl font-semibold mb-3">文档转原型</h2>
              <p className="text-gray-600">需求转HTML原型</p>
            </div>
          </Link>
        </div>
      </div>
    </div>
  );
}
