"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  listKnowledgeBases,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
import { listTeams, type TeamItem } from "@/lib/api/teams";

export default function AdminKnowledgeBasesPage() {
  const [teams, setTeams] = useState<TeamItem[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [items, setItems] = useState<KnowledgeBaseWithCount[]>([]);
  const [loading, setLoading] = useState(true);

  const selectedTeam = useMemo(
    () => teams.find((team) => team.id === selectedTeamId) ?? null,
    [selectedTeamId, teams],
  );

  useEffect(() => {
    const loadTeams = async () => {
      try {
        const list = await listTeams();
        setTeams(list);
        if (list.length > 0) {
          setSelectedTeamId((prev) => (prev && list.some((t) => t.id === prev) ? prev : list[0].id));
        } else {
          setSelectedTeamId(null);
        }
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "加载团队失败");
      }
    };

    void loadTeams();
  }, []);

  useEffect(() => {
    if (selectedTeamId == null) {
      setItems([]);
      setLoading(false);
      return;
    }

    const loadKnowledgeBases = async () => {
      setLoading(true);
      try {
        const rows = await listKnowledgeBases(selectedTeamId);
        setItems(rows);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "加载知识库失败");
      } finally {
        setLoading(false);
      }
    };

    void loadKnowledgeBases();
  }, [selectedTeamId]);

  return (
    <div className="px-6 py-8 sm:px-8">
      <h1 className="text-2xl font-semibold text-slate-900">知识库管理</h1>
      <p className="mt-2 text-sm text-slate-600">
        按所属团队查看知识库、文档数量与索引状态。若你管理多个团队，可在下方切换。
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <label className="text-sm text-slate-600">当前团队</label>
        <select
          value={selectedTeamId ?? ""}
          onChange={(event) =>
            setSelectedTeamId(event.target.value ? Number(event.target.value) : null)
          }
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none focus:border-slate-400"
        >
          {teams.length === 0 ? <option value="">暂无可管理团队</option> : null}
          {teams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name}
            </option>
          ))}
        </select>
        {selectedTeam ? (
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
            团队编码：{selectedTeam.code || "未设置"}
          </span>
        ) : null}
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {loading ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
            正在加载知识库...
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
            当前团队下还没有知识库。
          </div>
        ) : (
          items.map((item) => (
            <div
              key={item.id}
              className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">{item.name}</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {item.description || "暂无描述"}
                  </p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                  {item.status}
                </span>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3 text-sm text-slate-600">
                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                  文档数：{item.document_count}
                </div>
                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                  已索引：{item.indexed_document_count}
                </div>
                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                  处理中：{item.processing_document_count}
                </div>
                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                  失败数：{item.failed_document_count}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
