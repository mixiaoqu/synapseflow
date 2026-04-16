"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { Bot, ChevronRight, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { assistantsApi, type AssistantProfile } from "@/lib/api/assistants";
import { cn } from "@/lib/utils";

export default function AssistantDetailLayout({
  children,
}: {
  children: ReactNode;
}) {
  const params = useParams<{ assistantId: string }>();
  const pathname = usePathname();
  const assistantId = Number(params.assistantId);

  const [assistant, setAssistant] = useState<AssistantProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!Number.isFinite(assistantId) || assistantId <= 0) {
      setAssistant(null);
      setLoading(false);
      return;
    }

    void (async () => {
      setLoading(true);
      try {
        setAssistant(await assistantsApi.get(assistantId));
      } catch {
        setAssistant(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [assistantId]);

  const tabs = useMemo(
    () => [
      {
        href: `/admin/assistants/${assistantId}/edit`,
        label: "配置",
        active: pathname.includes(`/admin/assistants/${assistantId}/edit`),
      },
      {
        href: `/admin/assistants/${assistantId}/test`,
        label: "测试",
        active: pathname.includes(`/admin/assistants/${assistantId}/test`),
      },
    ],
    [assistantId, pathname],
  );

  return (
    <div className="min-h-screen bg-[#f8fafc] px-6 py-8 md:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-4 flex items-center gap-2 text-sm text-slate-500">
          <Link href="/admin/assistants" className="transition-colors hover:text-slate-900">
            Assistants
          </Link>
          <ChevronRight className="h-4 w-4" />
          <span className="truncate text-slate-700">
            {loading ? "加载中..." : assistant?.name ?? "助手详情"}
          </span>
        </div>

        <div className="rounded-[32px] border border-slate-200/80 bg-white p-8 shadow-sm">
          {loading ? (
            <div className="flex min-h-[120px] items-center justify-center">
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                正在加载助手详情...
              </div>
            </div>
          ) : (
            <>
              <div className="mb-6 flex items-center gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg shadow-emerald-500/20">
                  <Bot className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <h1 className="text-2xl font-semibold text-slate-900 truncate">
                    {assistant?.name ?? "未命名助手"}
                  </h1>
                  <p className="mt-1 text-sm text-slate-500 truncate">
                    {assistant?.description || assistant?.knowledge_base_name || "配置并测试当前助手"}
                  </p>
                </div>
                <Badge
                  className={cn(
                    "shrink-0",
                    assistant?.is_active
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-slate-100 text-slate-500",
                  )}
                >
                  {assistant?.is_active ? "已启用" : "已停用"}
                </Badge>
              </div>
            </>
          )}

          <div className="sticky top-0 z-10 mt-6 -mx-6 border-b border-slate-200 bg-white/95 px-6 pb-px backdrop-blur">
            <div className="flex space-x-6">
              {tabs.map((tab) => (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={cn(
                    "pb-3 text-sm transition-colors",
                    tab.active
                      ? "border-b-2 border-emerald-600 text-slate-900 font-medium"
                      : "text-slate-500 hover:text-slate-900",
                  )}
                >
                  {tab.label}
                </Link>
              ))}
            </div>
          </div>
        </div>

        <main className="pt-6">{children}</main>
      </div>
    </div>
  );
}
