"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Loader2,
  Pencil,
  Plus,
  Search,
  ShieldCheck,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
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
import { ROLE_OPTIONS } from "@/lib/auth/roles";
import {
  createUser,
  listUsers,
  updateUser,
  type AdminUserItem,
} from "@/lib/api/users";

/* ------------------------------------------------------------------ */
/*  Types & constants                                                  */
/* ------------------------------------------------------------------ */

type DraftUser = {
  username: string;
  email: string;
  full_name: string;
  password: string;
  role: string;
  is_active: boolean;
};

const EMPTY_DRAFT: DraftUser = {
  username: "",
  email: "",
  full_name: "",
  password: "",
  role: "end_user",
  is_active: true,
};

const USERNAME_MIN_LENGTH = 3;
const PASSWORD_MIN_LENGTH = 8;
const EMAIL_MIN_LENGTH = 5;
const FULL_NAME_MAX_LENGTH = 100;

const STATUS_OPTIONS = [
  { value: "all", label: "全部状态" },
  { value: "active", label: "启用中" },
  { value: "inactive", label: "已停用" },
] as const;

const ROLE_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  kb_admin: { bg: "bg-violet-50", text: "text-violet-700", dot: "bg-violet-500" },
  kb_reviewer: { bg: "bg-amber-50", text: "text-amber-700", dot: "bg-amber-500" },
  kb_editor: { bg: "bg-blue-50", text: "text-blue-700", dot: "bg-blue-500" },
  end_user: { bg: "bg-slate-50", text: "text-slate-600", dot: "bg-slate-400" },
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function roleLabel(role: string): string {
  return ROLE_OPTIONS.find((o) => o.value === role)?.label ?? role;
}

function roleColor(role: string) {
  return ROLE_COLORS[role] ?? ROLE_COLORS.end_user;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function getInitials(name?: string | null, username?: string): string {
  const src = name?.trim() || username || "?";
  // For Chinese names take first char; for ascii take up to 2 initials
  if (/[\u4e00-\u9fff]/.test(src)) return src.slice(0, 1);
  return src
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

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

function validateCreateDraft(draft: DraftUser): string | null {
  const username = draft.username.trim();
  const email = draft.email.trim();
  const fullName = draft.full_name.trim();

  if (!username || !email || !draft.password.trim()) {
    return "请先填写用户名、邮箱和初始密码";
  }
  if (username.length < USERNAME_MIN_LENGTH) {
    return `用户名至少需要 ${USERNAME_MIN_LENGTH} 个字符`;
  }
  if (email.length < EMAIL_MIN_LENGTH) {
    return "请输入有效的邮箱地址";
  }
  if (draft.password.length < PASSWORD_MIN_LENGTH) {
    return `初始密码至少需要 ${PASSWORD_MIN_LENGTH} 位`;
  }
  if (fullName.length > FULL_NAME_MAX_LENGTH) {
    return `姓名不能超过 ${FULL_NAME_MAX_LENGTH} 个字符`;
  }
  return null;
}

function validateEditDraft(draft: {
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
}): string | null {
  const email = draft.email.trim();
  const fullName = draft.full_name.trim();

  if (email.length < EMAIL_MIN_LENGTH) {
    return "请输入有效的邮箱地址";
  }
  if (fullName.length > FULL_NAME_MAX_LENGTH) {
    return `姓名不能超过 ${FULL_NAME_MAX_LENGTH} 个字符`;
  }
  return null;
}

/* ------------------------------------------------------------------ */
/*  Label + Input component for modals                                 */
/* ------------------------------------------------------------------ */

function FormField({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <label className="mb-1.5 block text-xs font-medium text-slate-500">
        {label}
      </label>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page component                                                     */
/* ------------------------------------------------------------------ */

export default function AdminUsersPage() {
  const [items, setItems] = useState<AdminUserItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<DraftUser>(EMPTY_DRAFT);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editItem, setEditItem] = useState<AdminUserItem | null>(null);
  const [editDraft, setEditDraft] = useState<{
    full_name: string;
    email: string;
    role: string;
    is_active: boolean;
  } | null>(null);

  /* ---- data loading ---- */

  const load = async () => {
    setLoading(true);
    try {
      setItems(await listUsers());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载用户列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  /* ---- filtering ---- */

  const filteredItems = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return items.filter((item) => {
      const matchesKeyword =
        !keyword ||
        item.username.toLowerCase().includes(keyword) ||
        item.email.toLowerCase().includes(keyword) ||
        (item.full_name || "").toLowerCase().includes(keyword);

      const matchesRole = roleFilter === "all" || item.role === roleFilter;
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "active" ? item.is_active : !item.is_active);

      return matchesKeyword && matchesRole && matchesStatus;
    });
  }, [items, roleFilter, search, statusFilter]);

  const summary = useMemo(() => {
    const total = items.length;
    const active = items.filter((i) => i.is_active).length;
    const admins = items.filter((i) => i.role !== "end_user").length;
    return { total, active, admins };
  }, [items]);

  /* ---- create ---- */

  const resetCreateDraft = () => setDraft(EMPTY_DRAFT);

  const handleCreate = async () => {
    const validationMessage = validateCreateDraft(draft);
    if (validationMessage) {
      toast.error(validationMessage);
      return;
    }
    if (!draft.username.trim() || !draft.email.trim() || !draft.password.trim()) {
      toast.error("请先填写用户名、邮箱和初始密码");
      return;
    }
    setCreating(true);
    try {
      const created = await createUser({
        username: draft.username.trim(),
        email: draft.email.trim(),
        full_name: draft.full_name.trim() || null,
        password: draft.password,
        role: draft.role,
        is_active: draft.is_active,
      });
      setItems((prev) => [created, ...prev]);
      resetCreateDraft();
      setCreateModalOpen(false);
      toast.success("用户已创建");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "创建用户失败");
    } finally {
      setCreating(false);
    }
  };

  /* ---- edit ---- */

  const openEdit = (item: AdminUserItem) => {
    setEditItem(item);
    setEditDraft({
      full_name: item.full_name ?? "",
      email: item.email,
      role: item.role,
      is_active: item.is_active,
    });
  };

  const closeEdit = () => {
    setEditItem(null);
    setEditDraft(null);
  };

  const handleSaveEdit = async () => {
    if (!editItem || !editDraft) return;
    const validationMessage = validateEditDraft(editDraft);
    if (validationMessage) {
      toast.error(validationMessage);
      return;
    }
    setSavingId(editItem.id);
    try {
      const updated = await updateUser(editItem.id, {
        full_name: editDraft.full_name.trim(),
        email: editDraft.email.trim(),
        role: editDraft.role,
        is_active: editDraft.is_active,
      });
      setItems((prev) => prev.map((u) => (u.id === editItem.id ? updated : u)));
      closeEdit();
      toast.success("用户信息已更新");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "更新用户失败");
    } finally {
      setSavingId(null);
    }
  };

  /* ---- quick toggle status ---- */

  const toggleStatus = async (item: AdminUserItem) => {
    setSavingId(item.id);
    try {
      const updated = await updateUser(item.id, { is_active: !item.is_active });
      setItems((prev) => prev.map((u) => (u.id === item.id ? updated : u)));
      toast.success(updated.is_active ? "账号已启用" : "账号已停用");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "操作失败");
    } finally {
      setSavingId(null);
    }
  };

  /* ================================================================ */
  /*  Render                                                           */
  /* ================================================================ */

  const activeFilters =
    search.trim() !== "" || roleFilter !== "all" || statusFilter !== "all";

  return (
    <>
      <AdminPage>
        <AdminPageHeader
          title="用户管理"
          description="管理系统中所有用户的账号信息、角色权限和启停状态。"
          actions={
            <Button
              type="button"
              className="gap-2 rounded-2xl"
              onClick={() => {
                resetCreateDraft();
                setCreateModalOpen(true);
              }}
            >
              <UserPlus className="h-4 w-4" />
              新建用户
            </Button>
          }
        />

        {/* ---- Stat cards ---- */}
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100">
              <Users className="h-5 w-5 text-slate-600" />
            </div>
            <div>
              <p className="text-2xl font-semibold text-slate-900">{summary.total}</p>
              <p className="text-xs text-slate-500">用户总数</p>
            </div>
          </div>
          <div className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50">
              <div className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
            </div>
            <div>
              <p className="text-2xl font-semibold text-slate-900">{summary.active}</p>
              <p className="text-xs text-slate-500">启用中</p>
            </div>
          </div>
          <div className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-violet-50">
              <ShieldCheck className="h-5 w-5 text-violet-600" />
            </div>
            <div>
              <p className="text-2xl font-semibold text-slate-900">{summary.admins}</p>
              <p className="text-xs text-slate-500">后台角色</p>
            </div>
          </div>
        </div>

        {/* ---- Filters ---- */}
        <AdminPageContent>
          <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-5 py-4">
            <div className="relative min-w-[260px] flex-1">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索用户名、姓名或邮箱…"
                className="h-10 w-full rounded-xl border border-slate-200 bg-slate-50/60 pl-10 pr-4 text-sm outline-none transition placeholder:text-slate-400 focus:border-slate-300 focus:bg-white focus:ring-1 focus:ring-slate-200"
              />
            </div>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="h-10 min-w-[150px] cursor-pointer rounded-xl border border-slate-200 bg-slate-50/60 px-3 text-sm outline-none transition focus:border-slate-300 focus:bg-white"
            >
              <option value="all">全部角色</option>
              {ROLE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-10 min-w-[130px] cursor-pointer rounded-xl border border-slate-200 bg-slate-50/60 px-3 text-sm outline-none transition focus:border-slate-300 focus:bg-white"
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            {activeFilters && (
              <button
                type="button"
                onClick={() => {
                  setSearch("");
                  setRoleFilter("all");
                  setStatusFilter("all");
                }}
                className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-3 w-3" />
                清除筛选
              </button>
            )}
          </div>

          {/* ---- Table ---- */}
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left">
                  <th className="px-5 py-3 text-xs font-medium uppercase tracking-wider text-slate-400">
                    用户
                  </th>
                  <th className="px-5 py-3 text-xs font-medium uppercase tracking-wider text-slate-400">
                    角色
                  </th>
                  <th className="px-5 py-3 text-xs font-medium uppercase tracking-wider text-slate-400">
                    状态
                  </th>
                  <th className="px-5 py-3 text-xs font-medium uppercase tracking-wider text-slate-400">
                    创建时间
                  </th>
                  <th className="px-5 py-3 text-xs font-medium uppercase tracking-wider text-slate-400">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <Skeleton className="h-10 w-10 rounded-full" />
                          <div className="space-y-2">
                            <Skeleton className="h-4 w-28" />
                            <Skeleton className="h-3 w-36" />
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <Skeleton className="h-6 w-20 rounded-full" />
                      </td>
                      <td className="px-5 py-4">
                        <Skeleton className="h-6 w-16 rounded-full" />
                      </td>
                      <td className="px-5 py-4">
                        <Skeleton className="h-4 w-32" />
                      </td>
                      <td className="px-5 py-4">
                        <Skeleton className="h-8 w-8 rounded-lg" />
                      </td>
                    </tr>
                  ))
                ) : filteredItems.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-16 text-center">
                      <div className="mx-auto flex max-w-xs flex-col items-center">
                        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100">
                          <Search className="h-6 w-6 text-slate-400" />
                        </div>
                        <p className="mt-4 font-medium text-slate-700">
                          {activeFilters ? "没有匹配的用户" : "暂无用户"}
                        </p>
                        <p className="mt-1 text-sm text-slate-400">
                          {activeFilters
                            ? "试试调整筛选条件或关键词"
                            : "点击右上方「新建用户」来添加第一个用户"}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredItems.map((item) => {
                    const rc = roleColor(item.role);
                    return (
                      <tr
                        key={item.id}
                        className="group transition-colors hover:bg-slate-50/70"
                      >
                        {/* User info cell */}
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-3">
                            <div
                              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${avatarPalette(item.id)}`}
                            >
                              {getInitials(item.full_name, item.username)}
                            </div>
                            <div className="min-w-0">
                              <p className="truncate font-medium text-slate-900">
                                {item.full_name || item.username}
                              </p>
                              <p className="truncate text-xs text-slate-400">
                                @{item.username}
                                <span className="mx-1.5 text-slate-200">·</span>
                                {item.email}
                              </p>
                            </div>
                          </div>
                        </td>

                        {/* Role badge */}
                        <td className="px-5 py-4">
                          <span
                            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${rc.bg} ${rc.text}`}
                          >
                            <span
                              className={`inline-block h-1.5 w-1.5 rounded-full ${rc.dot}`}
                            />
                            {roleLabel(item.role)}
                          </span>
                        </td>

                        {/* Status toggle */}
                        <td className="px-5 py-4">
                          <button
                            type="button"
                            disabled={savingId === item.id}
                            onClick={() => void toggleStatus(item)}
                            className="group/toggle inline-flex items-center gap-2 rounded-full px-0.5 text-sm disabled:opacity-50"
                          >
                            <span
                              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors ${
                                item.is_active ? "bg-emerald-500" : "bg-slate-300"
                              }`}
                            >
                              <span
                                className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform ${
                                  item.is_active ? "translate-x-[18px]" : "translate-x-[3px]"
                                }`}
                              />
                            </span>
                            <span
                              className={`text-xs font-medium ${
                                item.is_active ? "text-emerald-700" : "text-slate-400"
                              }`}
                            >
                              {item.is_active ? "启用" : "停用"}
                            </span>
                          </button>
                        </td>

                        {/* Created at */}
                        <td className="px-5 py-4 text-xs text-slate-400">
                          {formatDate(item.created_at)}
                        </td>

                        {/* Actions */}
                        <td className="px-5 py-4">
                          <button
                            type="button"
                            onClick={() => openEdit(item)}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
                            title="编辑用户"
                          >
                            <Pencil className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Bottom bar with count */}
          {!loading && filteredItems.length > 0 && (
            <div className="border-t border-slate-100 px-5 py-3 text-xs text-slate-400">
              共 {filteredItems.length} 条记录
              {activeFilters && `（全部 ${items.length} 条）`}
            </div>
          )}
        </AdminPageContent>
      </AdminPage>

      {/* Create Modal */}
      <Dialog open={createModalOpen} onOpenChange={(o) => {
        if (!o) { setCreateModalOpen(false); resetCreateDraft(); }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建用户</DialogTitle>
            <DialogDescription>创建后可在列表中继续管理</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="用户名 *">
                <input
                  value={draft.username}
                  minLength={USERNAME_MIN_LENGTH}
                  onChange={(e) =>
                    setDraft((p) => ({ ...p, username: e.target.value }))
                  }
                  placeholder="如 zhangsan"
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition placeholder:text-slate-300 focus:border-slate-400 focus:ring-1 focus:ring-slate-200"
                />
              </FormField>
              <FormField label="姓名">
                <input
                  value={draft.full_name}
                  maxLength={FULL_NAME_MAX_LENGTH}
                  onChange={(e) =>
                    setDraft((p) => ({ ...p, full_name: e.target.value }))
                  }
                  placeholder="如 张三"
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition placeholder:text-slate-300 focus:border-slate-400 focus:ring-1 focus:ring-slate-200"
                />
              </FormField>
            </div>
            <FormField label="邮箱 *">
              <input
                value={draft.email}
                minLength={EMAIL_MIN_LENGTH}
                onChange={(e) =>
                  setDraft((p) => ({ ...p, email: e.target.value }))
                }
                type="email"
                placeholder="user@example.com"
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition placeholder:text-slate-300 focus:border-slate-400 focus:ring-1 focus:ring-slate-200"
              />
            </FormField>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="初始密码 *">
                <input
                  value={draft.password}
                  type="password"
                  minLength={PASSWORD_MIN_LENGTH}
                  onChange={(e) =>
                    setDraft((p) => ({ ...p, password: e.target.value }))
                  }
                  placeholder={`至少 ${PASSWORD_MIN_LENGTH} 位`}
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition placeholder:text-slate-300 focus:border-slate-400 focus:ring-1 focus:ring-slate-200"
                />
              </FormField>
              <FormField label="角色">
                <select
                  value={draft.role}
                  onChange={(e) =>
                    setDraft((p) => ({ ...p, role: e.target.value }))
                  }
                  className="h-10 w-full cursor-pointer rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-slate-400 focus:ring-1 focus:ring-slate-200"
                >
                  {ROLE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </FormField>
            </div>
            <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-700 transition hover:bg-slate-50">
              <span
                className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
                  draft.is_active ? "bg-emerald-500" : "bg-slate-300"
                }`}
              >
                <span
                  className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform ${
                    draft.is_active ? "translate-x-[18px]" : "translate-x-[3px]"
                  }`}
                />
              </span>
              <input
                type="checkbox"
                checked={draft.is_active}
                onChange={(e) =>
                  setDraft((p) => ({ ...p, is_active: e.target.checked }))
                }
                className="sr-only"
              />
              创建后立即启用账号
            </label>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => { setCreateModalOpen(false); resetCreateDraft(); }}
            >
              取消
            </Button>
            <Button
              type="button"
              disabled={creating}
              onClick={() => void handleCreate()}
            >
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              创建用户
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Modal */}
      <Dialog open={!!editItem} onOpenChange={(o) => { if (!o) closeEdit(); }}>
        <DialogContent>
          <DialogHeader>
            <div className="flex items-center gap-3">
              <div className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold ${avatarPalette(editItem?.id ?? 0)}`}>
                {editItem && getInitials(editItem.full_name, editItem.username)}
              </div>
              <div>
                <DialogTitle>编辑用户</DialogTitle>
                <DialogDescription>@{editItem?.username}</DialogDescription>
              </div>
            </div>
          </DialogHeader>
          <div className="space-y-4">
            <FormField label="姓名">
              <input
                value={editDraft?.full_name ?? ""}
                maxLength={FULL_NAME_MAX_LENGTH}
                onChange={(e) =>
                  setEditDraft((p) => p && { ...p, full_name: e.target.value })
                }
                placeholder="姓名"
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition placeholder:text-slate-300 focus:border-slate-400 focus:ring-1 focus:ring-slate-200"
              />
            </FormField>
            <FormField label="邮箱">
              <input
                value={editDraft?.email ?? ""}
                minLength={EMAIL_MIN_LENGTH}
                onChange={(e) =>
                  setEditDraft((p) => p && { ...p, email: e.target.value })
                }
                type="email"
                placeholder="邮箱"
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition placeholder:text-slate-300 focus:border-slate-400 focus:ring-1 focus:ring-slate-200"
              />
            </FormField>
            <FormField label="角色">
              <select
                value={editDraft?.role ?? "end_user"}
                onChange={(e) =>
                  setEditDraft((p) => p && { ...p, role: e.target.value })
                }
                className="h-10 w-full cursor-pointer rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-slate-400 focus:ring-1 focus:ring-slate-200"
              >
                {ROLE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </FormField>
            <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-700 transition hover:bg-slate-50">
              <span
                className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
                  editDraft?.is_active ? "bg-emerald-500" : "bg-slate-300"
                }`}
              >
                <span
                  className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform ${
                    editDraft?.is_active ? "translate-x-[18px]" : "translate-x-[3px]"
                  }`}
                />
              </span>
              <input
                type="checkbox"
                checked={editDraft?.is_active ?? false}
                onChange={(e) =>
                  setEditDraft((p) =>
                    p && { ...p, is_active: e.target.checked }
                  )
                }
                className="sr-only"
              />
              {editDraft?.is_active ? "账号已启用" : "账号已停用"}
            </label>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={closeEdit}>
              取消
            </Button>
            <Button
              type="button"
              disabled={savingId === editItem?.id}
              onClick={() => void handleSaveEdit()}
            >
              {savingId === editItem?.id ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              保存修改
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
