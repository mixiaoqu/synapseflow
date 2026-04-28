"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Building2,
  Loader2,
  Plus,
  Search,
  Trash2,
  UserMinus,
  Users,
  Pencil,
  MoreHorizontal,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  AdminPage,
  AdminPageContent,
  AdminPageHeader,
} from "@/components/admin/layout/AdminPage";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  addTeamMember,
  createTeam,
  deleteTeam,
  deleteTeamMember,
  listTeamMembers,
  listTeams,
  updateTeam,
  updateTeamMember,
  type TeamItem,
  type TeamMemberItem,
} from "@/lib/api/teams";
import { listUsers, type AdminUserItem } from "@/lib/api/users";

/* ------------------------------------------------------------------ */
/*  Types & constants                                                    */
/* ------------------------------------------------------------------ */

type DraftTeam = {
  name: string;
  code: string;
  description: string;
};

const EMPTY_TEAM: DraftTeam = { name: "", code: "", description: "" };

const TEAM_ROLE_LABELS: Record<string, string> = {
  owner: "所有者",
  admin: "管理员",
  member: "成员",
};

const AVATAR_PALETTES = [
  "bg-blue-100 text-blue-700",
  "bg-emerald-100 text-emerald-700",
  "bg-violet-100 text-violet-700",
  "bg-amber-100 text-amber-700",
  "bg-rose-100 text-rose-700",
  "bg-cyan-100 text-cyan-700",
  "bg-fuchsia-100 text-fuchsia-700",
  "bg-teal-100 text-teal-700",
];

function avatarPalette(id: number) {
  return AVATAR_PALETTES[id % AVATAR_PALETTES.length];
}

function getInitials(name?: string | null, username?: string): string {
  const src = name?.trim() || username || "?";
  if (/[\u4e00-\u9fff]/.test(src)) return src.slice(0, 1);
  return src
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    year: "numeric",
  }).format(d);
}

/* ------------------------------------------------------------------ */
/*  Confirm dialog                                                       */
/* ------------------------------------------------------------------ */

function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  loading,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  loading: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{message}</DialogDescription>
        </DialogHeader>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel} disabled={loading}>
            取消
          </Button>
          <Button
            variant="destructive"
            onClick={onConfirm}
            disabled={loading}
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ */
/*  Team form dialog                                                     */
/* ------------------------------------------------------------------ */

function TeamFormDialog({
  open,
  team,
  loading,
  onSubmit,
  onClose,
}: {
  open: boolean;
  team: TeamItem | null;
  loading: boolean;
  onSubmit: (draft: DraftTeam) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<DraftTeam>(EMPTY_TEAM);

  useEffect(() => {
    if (open) {
      setDraft(
        team
          ? {
              name: team.name,
              code: team.code ?? "",
              description: team.description ?? "",
            }
          : EMPTY_TEAM
      );
    }
  }, [open, team]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft.name.trim()) {
      toast.error("请填写团队名称");
      return;
    }
    onSubmit({ ...draft });
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{team ? "编辑团队" : "新建团队"}</DialogTitle>
          <DialogDescription>
            {team
              ? `正在编辑团队「${team.name}」`
              : "创建一个新团队，用于组织和管理成员"}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-500">
              团队名称 <span className="text-red-500">*</span>
            </label>
            <input
              value={draft.name}
              onChange={(e) =>
                setDraft((p) => ({ ...p, name: e.target.value }))
              }
              placeholder="例如 产品部"
              className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-slate-400 focus:ring-1 focus:ring-slate-200"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-500">
              团队编码
            </label>
            <input
              value={draft.code}
              onChange={(e) =>
                setDraft((p) => ({ ...p, code: e.target.value }))
              }
              placeholder="如 PRD"
              className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-slate-400 focus:ring-1 focus:ring-slate-200"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-500">
              团队描述
            </label>
            <textarea
              value={draft.description}
              onChange={(e) =>
                setDraft((p) => ({ ...p, description: e.target.value }))
              }
              placeholder="简要描述团队的职能范围…"
              rows={3}
              className="w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-slate-400 focus:ring-1 focus:ring-slate-200"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              取消
            </Button>
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {team ? "保存修改" : "创建团队"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ */
/*  Member panel                                                         */
/* ------------------------------------------------------------------ */

function MemberPanel({
  team,
  members,
  users,
  userMap,
  onClose,
  onUpdateRole,
  onRemoveMember,
  onAddMember,
}: {
  team: TeamItem;
  members: TeamMemberItem[];
  users: AdminUserItem[];
  userMap: Map<number, AdminUserItem>;
  onClose: () => void;
  onUpdateRole: (member: TeamMemberItem, role: string) => Promise<void>;
  onRemoveMember: (member: TeamMemberItem) => void;
  onAddMember: (userId: number, role: string) => Promise<void>;
}) {
  const [memberSearch, setMemberSearch] = useState("");
  const [memberUserId, setMemberUserId] = useState<number | null>(null);
  const [memberRole, setMemberRole] = useState("member");
  const [memberLoading, setMemberLoading] = useState(false);
  const [updatingRoleId, setUpdatingRoleId] = useState<number | null>(null);

  const memberIds = useMemo(
    () => new Set(members.map((m) => m.user_id)),
    [members]
  );

  const availableUsers = useMemo(() => {
    const kw = memberSearch.trim().toLowerCase();
    return users.filter((u) => {
      if (memberIds.has(u.id)) return false;
      if (!kw) return true;
      return (
        (u.full_name || "").toLowerCase().includes(kw) ||
        u.username.toLowerCase().includes(kw) ||
        u.email.toLowerCase().includes(kw)
      );
    });
  }, [users, memberIds, memberSearch]);

  const handleAdd = async () => {
    if (!memberUserId) {
      toast.error("请先选择一个用户");
      return;
    }
    setMemberLoading(true);
    try {
      await onAddMember(memberUserId, memberRole);
      setMemberUserId(null);
      setMemberRole("member");
      setMemberSearch("");
    } finally {
      setMemberLoading(false);
    }
  };

  const handleRoleChange = async (member: TeamMemberItem, role: string) => {
    setUpdatingRoleId(member.id);
    try {
      await onUpdateRole(member, role);
    } finally {
      setUpdatingRoleId(null);
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
        <button
          type="button"
          onClick={onClose}
          className="flex items-center gap-1 text-sm text-slate-500 transition-colors hover:text-slate-800"
        >
          <ArrowLeft className="h-4 w-4" />
          返回
        </button>
        <div className="h-4 w-px bg-slate-200" />
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-slate-400" />
          <span className="font-medium text-slate-800">{team.name}</span>
          <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
            {members.length} 人
          </span>
        </div>
      </div>

      {/* Add member */}
      <div className="relative border-b border-slate-100 px-5 py-4">
        <div className="grid gap-3 sm:grid-cols-[1fr_120px_auto]">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-500">
              添加成员
            </label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={memberSearch}
                onChange={(e) => {
                  setMemberSearch(e.target.value);
                  setMemberUserId(null);
                }}
                placeholder="搜索姓名、用户名或邮箱…"
                className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-800 outline-none transition focus:border-slate-400"
              />
            </div>
            {/* User picker dropdown */}
            {memberSearch.trim() !== "" && availableUsers.length > 0 && (
              <div className="absolute left-0 top-full z-10 mt-1 w-full max-w-[280px] rounded-xl border border-slate-200 bg-white py-1 shadow-lg">
                {availableUsers.slice(0, 6).map((user) => (
                  <button
                    key={user.id}
                    type="button"
                    onClick={() => {
                      setMemberUserId(user.id);
                      setMemberSearch(user.full_name || user.username);
                    }}
                    className={`flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors ${
                      memberUserId === user.id
                        ? "bg-blue-50 text-blue-700"
                        : "hover:bg-slate-50"
                    }`}
                  >
                    <div
                      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold ${avatarPalette(
                        user.id
                      )}`}
                    >
                      {getInitials(user.full_name, user.username)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">
                        {user.full_name || user.username}
                      </p>
                      <p className="truncate text-xs text-slate-400">
                        {user.email}
                      </p>
                    </div>
                  </button>
                ))}
                {availableUsers.length > 6 && (
                  <p className="px-3 py-1.5 text-xs text-slate-400">
                    还有 {availableUsers.length - 6} 位用户…
                  </p>
                )}
              </div>
            )}
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-500">
              角色
            </label>
            <select
              value={memberRole}
              onChange={(e) => setMemberRole(e.target.value)}
              className="h-10 w-full cursor-pointer rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-slate-400"
            >
              {Object.entries(TEAM_ROLE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <Button
              type="button"
              size="sm"
              className="h-10 w-full rounded-xl"
              disabled={
                memberLoading || !memberUserId || availableUsers.length === 0
              }
              onClick={handleAdd}
            >
              {memberLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              添加
            </Button>
          </div>
        </div>
        {memberSearch.trim() !== "" &&
          availableUsers.length === 0 &&
          memberUserId === null && (
            <p className="mt-2 text-xs text-slate-400">
              没有匹配的用户，或所有用户已添加
            </p>
          )}
      </div>

      {/* Member list */}
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {members.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-xs text-slate-400">
            <Users className="mb-2 h-8 w-8" />
            还没有成员
          </div>
        ) : (
          <div className="space-y-2">
            {members.map((member) => {
              const user = userMap.get(member.user_id);
              const isInactive = user && !user.is_active;
              return (
                <div
                  key={member.id}
                  className={`flex items-center gap-3 rounded-xl border border-slate-100 bg-white px-4 py-3 ${
                    isInactive ? "opacity-50" : ""
                  }`}
                >
                  <div
                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${avatarPalette(
                      member.user_id
                    )}`}
                  >
                    {getInitials(user?.full_name, user?.username)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-800">
                      {user?.full_name || user?.username || `用户 #${member.user_id}`}
                    </p>
                    <p className="text-xs text-slate-400">
                      {user?.email || `user_id=${member.user_id}`}
                      {isInactive && " · 已停用"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {user?.role && (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                        {TEAM_ROLE_LABELS[user.role] ?? user.role}
                      </span>
                    )}
                    <select
                      value={member.role}
                      disabled={updatingRoleId === member.id}
                      onChange={(e) => void handleRoleChange(member, e.target.value)}
                      className="cursor-pointer rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs outline-none transition focus:border-slate-400"
                    >
                      {Object.entries(TEAM_ROLE_LABELS).map(([k, v]) => (
                        <option key={k} value={k}>
                          {v}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => onRemoveMember(member)}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-500 transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-600"
                    >
                      <UserMinus className="h-3 w-3" />
                      移除
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main page                                                            */
/* ------------------------------------------------------------------ */

export default function AdminTeamsPage() {
  const [teams, setTeams] = useState<TeamItem[]>([]);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [members, setMembers] = useState<TeamMemberItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Dialog states
  const [teamDialogOpen, setTeamDialogOpen] = useState(false);
  const [editingTeam, setEditingTeam] = useState<TeamItem | null>(null);
  const [teamFormLoading, setTeamFormLoading] = useState(false);

  // Member panel state
  const [activeTeam, setActiveTeam] = useState<TeamItem | null>(null);
  const [memberPanelOpen, setMemberPanelOpen] = useState(false);

  // Confirm states
  const [deleteTeamTarget, setDeleteTeamTarget] = useState<TeamItem | null>(null);
  const [removeMemberTarget, setRemoveMemberTarget] = useState<TeamMemberItem | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [removeLoading, setRemoveLoading] = useState(false);

  const userMap = useMemo(() => new Map(users.map((u) => [u.id, u])), [users]);

  /* ---- data loading ---- */
  const load = async () => {
    setLoading(true);
    try {
      const [nextTeams, nextUsers] = await Promise.all([
        listTeams(),
        listUsers(),
      ]);
      setTeams(nextTeams);
      setUsers(nextUsers);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  /* ---- team actions ---- */
  const openCreateDialog = () => {
    setEditingTeam(null);
    setTeamDialogOpen(true);
  };

  const openEditDialog = (team: TeamItem) => {
    setEditingTeam(team);
    setTeamDialogOpen(true);
  };

  const handleTeamSubmit = async (draft: DraftTeam) => {
    setTeamFormLoading(true);
    try {
      if (editingTeam) {
        const updated = await updateTeam(editingTeam.id, {
          name: draft.name.trim(),
          code: draft.code.trim() || null,
          description: draft.description.trim() || null,
        });
        setTeams((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
        if (activeTeam?.id === updated.id) setActiveTeam(updated);
        toast.success("团队信息已更新");
      } else {
        const created = await createTeam({
          name: draft.name.trim(),
          code: draft.code.trim() || null,
          description: draft.description.trim() || null,
        });
        setTeams((prev) => [created, ...prev]);
        toast.success("团队已创建");
      }
      setTeamDialogOpen(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "操作失败");
    } finally {
      setTeamFormLoading(false);
    }
  };

  const handleDeleteTeam = async () => {
    if (!deleteTeamTarget) return;
    setDeleteLoading(true);
    try {
      await deleteTeam(deleteTeamTarget.id);
      setTeams((prev) => prev.filter((t) => t.id !== deleteTeamTarget.id));
      if (activeTeam?.id === deleteTeamTarget.id) {
        setActiveTeam(null);
        setMemberPanelOpen(false);
      }
      toast.success("团队已删除");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "删除失败");
    } finally {
      setDeleteLoading(false);
      setDeleteTeamTarget(null);
    }
  };

  /* ---- member actions ---- */
  const handleOpenMemberPanel = async (team: TeamItem) => {
    setActiveTeam(team);
    setMemberPanelOpen(true);
    try {
      const data = await listTeamMembers(team.id);
      setMembers(data);
    } catch {
      setMembers([]);
    }
  };

  const handleCloseMemberPanel = () => {
    setMemberPanelOpen(false);
    setActiveTeam(null);
    setMembers([]);
  };

  const handleAddMember = async (userId: number, role: string) => {
    if (!activeTeam) return;
    const created = await addTeamMember(activeTeam.id, { user_id: userId, role });
    setMembers((prev) => [...prev, created]);
    toast.success("成员已加入团队");
  };

  const handleUpdateRole = async (member: TeamMemberItem, role: string) => {
    if (!activeTeam) return;
    const updated = await updateTeamMember(activeTeam.id, member.user_id, { role });
    setMembers((prev) =>
      prev.map((m) =>
        m.user_id === updated.user_id && m.team_id === updated.team_id ? updated : m
      )
    );
    toast.success("成员角色已更新");
  };

  const handleRemoveMember = async () => {
    if (!activeTeam || !removeMemberTarget) return;
    setRemoveLoading(true);
    try {
      await deleteTeamMember(activeTeam.id, removeMemberTarget.user_id);
      setMembers((prev) =>
        prev.filter((m) => m.user_id !== removeMemberTarget.user_id)
      );
      toast.success("成员已移出团队");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "移除失败");
    } finally {
      setRemoveLoading(false);
      setRemoveMemberTarget(null);
    }
  };

  /* ---- member count map ---- */
  const teamMemberCounts = useMemo(() => {
    const counts = new Map<number, number>();
    // We don't have member counts from listTeams, so show "—" until panel opens
    return counts;
  }, []);

  /* ================================================================ */
  /*  Render                                                           */
  /* ================================================================ */

  return (
    <AdminPage>
      <AdminPageHeader
        title="团队管理"
        description="维护组织团队，把账号分配到具体团队中。"
        actions={
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 text-xs text-slate-400 sm:flex">
              <Users className="h-4 w-4" />
              {teams.length} 个团队 · {users.length} 个账号
            </div>
            <Button type="button" onClick={openCreateDialog} className="gap-2 rounded-2xl">
              <Plus className="h-4 w-4" />
              新建团队
            </Button>
          </div>
        }
      />

      <div className="flex gap-6">
        {/* Main content */}
        <AdminPageContent className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {/* Table area */}
          <div className="min-h-0 flex-1 overflow-auto">
            <div className="px-6 py-5 sm:px-8">
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-slate-400" />
                  <h2 className="text-sm font-semibold text-slate-800">团队列表</h2>
                  <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
                    {teams.length}
                  </span>
                </div>
              </div>

              {loading ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-14 rounded-xl bg-slate-100" />
                  ))}
                </div>
              ) : teams.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 py-16 text-xs text-slate-400">
                  <Building2 className="mb-3 h-10 w-10 text-slate-300" />
                  <p className="mb-1 font-medium text-slate-500">还没有团队</p>
                  <p>点击上方「新建团队」创建第一个团队</p>
                </div>
              ) : (
                <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                  <table className="min-w-full text-sm">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-400">
                          团队名称
                        </th>
                        <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-400">
                          编码
                        </th>
                        <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-400">
                          描述
                        </th>
                        <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-400">
                          创建时间
                        </th>
                        <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wider text-slate-400">
                          操作
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {teams.map((team) => (
                        <tr
                          key={team.id}
                          className="transition-colors hover:bg-slate-50"
                        >
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-2.5">
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-xs font-semibold text-slate-600">
                              {team.name.slice(0, 1)}
                            </div>
                            <span className="font-medium text-slate-800">
                              {team.name}
                            </span>
                          </div>
                        </td>
                        <td className="px-5 py-4">
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                            {team.code || "—"}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <span className="text-sm text-slate-500">
                            {team.description || "—"}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <span className="text-sm text-slate-400">
                            {formatDate(team.created_at)}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              type="button"
                              onClick={() => void handleOpenMemberPanel(team)}
                              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-600"
                            >
                              <Users className="h-3 w-3" />
                              成员
                            </button>
                            <button
                              type="button"
                              onClick={() => openEditDialog(team)}
                              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                            >
                              <Pencil className="h-3 w-3" />
                              编辑
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeleteTeamTarget(team)}
                              className="inline-flex items-center gap-1 rounded-lg border border-red-100 px-2.5 py-1.5 text-xs text-red-500 transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-600"
                            >
                              <Trash2 className="h-3 w-3" />
                              删除
                            </button>
                          </div>
                        </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </AdminPageContent>

      {/* Member panel */}
      {memberPanelOpen && activeTeam && (
        <div className="w-96 shrink-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <MemberPanel
            team={activeTeam}
            members={members}
            users={users}
            userMap={userMap}
            onClose={handleCloseMemberPanel}
            onUpdateRole={handleUpdateRole}
            onRemoveMember={(m) => setRemoveMemberTarget(m)}
            onAddMember={handleAddMember}
          />
        </div>
      )}
      </div>

      {/* Dialogs */}
      <TeamFormDialog
        open={teamDialogOpen}
        team={editingTeam}
        loading={teamFormLoading}
        onSubmit={handleTeamSubmit}
        onClose={() => setTeamDialogOpen(false)}
      />

      <ConfirmDialog
        open={deleteTeamTarget !== null}
        title="确认删除团队"
        message={
          deleteTeamTarget
            ? `即将删除团队「${deleteTeamTarget.name}」，该操作不可恢复，团队内的成员关系也将一并清除。`
            : ""
        }
        confirmLabel="确认删除"
        loading={deleteLoading}
        onConfirm={handleDeleteTeam}
        onCancel={() => setDeleteTeamTarget(null)}
      />

      <ConfirmDialog
        open={removeMemberTarget !== null}
        title="确认移除成员"
        message={
          removeMemberTarget
            ? `即将把用户「${
                userMap.get(removeMemberTarget.user_id)?.full_name ||
                userMap.get(removeMemberTarget.user_id)?.username ||
                `用户 #${removeMemberTarget.user_id}`
              }」从团队中移除。`
            : ""
        }
        confirmLabel="确认移除"
        loading={removeLoading}
        onConfirm={handleRemoveMember}
        onCancel={() => setRemoveMemberTarget(null)}
      />
    </AdminPage>
  );
}
