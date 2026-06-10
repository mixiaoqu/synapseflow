<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Delete,
  EditPen,
  Plus,
  Refresh,
  Search,
  User,
} from "@element-plus/icons-vue";

import AdminBulkActions from "@/app/components/admin/AdminBulkActions.vue";
import AdminDataTable from "@/app/components/admin/AdminDataTable.vue";
import AdminDialog from "@/app/components/admin/AdminDialog.vue";
import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminPagination from "@/app/components/admin/AdminPagination.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import {
  addTeamMember,
  bulkActionTeams,
  bulkDeleteTeamMembers,
  bulkUpdateTeamMembersRole,
  createTeam,
  deleteTeam,
  deleteTeamMember,
  listTeamMembers,
  listTeams,
  updateTeam,
  updateTeamMember,
} from "@/shared/api/teams";
import { listUsers } from "@/shared/api/users";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import { useAuthStore } from "@/stores/auth";
import { useTeamScopeStore } from "@/stores/team-scope";
import { TEAM_ROLE_LABELS } from "@/shared/types/team";
import type { TeamRole, TeamSummary, TeamMember } from "@/shared/types/team";
import type { AdminUser } from "@/shared/types/user";

const AVATAR_PALETTES = [
  "background:var(--admin-primary-soft);color:var(--admin-primary-hover)",
  "background:#ecfdf5;color:#059669",
  "background:#f5f3ff;color:#7c3aed",
  "background:#fffbeb;color:#d97706",
  "background:#fff1f2;color:#e11d48",
  "background:#ecfeff;color:#0891b2",
  "background:#fdf4ff;color:#c026d3",
  "background:#f0fdfa;color:#0d9488",
];

/** 根据用户 ID 生成头像背景色 */
function avatarStyle(id: number) {
  return AVATAR_PALETTES[id % AVATAR_PALETTES.length];
}

/** 提取姓名首字（中文取第一个字，英文取首字母缩写） */
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

/** 格式化日期 */
function formatDate(value?: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(d);
}

const teamScopeStore = useTeamScopeStore();
const authStore = useAuthStore();
const TEAM_ROLE_OPTIONS = Object.entries(TEAM_ROLE_LABELS).map(([value, label]) => ({
  value: value as TeamRole,
  label,
}));

const teams = ref<TeamSummary[]>([]);
const users = ref<AdminUser[]>([]);
const loading = ref(false);
const loadError = ref<unknown>(null);
const hasLoadedData = ref(false);
const userOptionsLoading = ref(false);
const selectedTeamIds = ref<number[]>([]);
const teamBatchActionLoading = ref<"" | "delete">("");

const teamDialogVisible = ref(false);
const editingTeam = ref<TeamSummary | null>(null);
const teamFormLoading = ref(false);
const teamForm = ref({ name: "", code: "", description: "" });

const memberDialogVisible = ref(false);
const activeTeam = ref<TeamSummary | null>(null);
const members = ref<TeamMember[]>([]);
const memberLoading = ref(false);
const memberLoaded = ref(false);
const updatingMemberId = ref<number | null>(null);

/** 新建团队时选中的初始成员 ID 列表 */
const createMemberIds = ref<number[]>([]);
/** 成员管理弹窗左侧搜索关键词 */
const memberSearchKeyword = ref("");
/** 成员管理弹窗右侧搜索关键词 */
const currentMemberSearchKeyword = ref("");
/** 成员管理弹窗右侧角色过滤 */
const currentMemberRoleFilter = ref<"all" | TeamRole>("all");
/** 成员管理弹窗左侧待添加的用户 ID 列表 */
const pendingAddIds = ref<number[]>([]);
/** 成员管理弹窗右侧选中的成员用户 ID 列表 */
const selectedMemberUserIds = ref<number[]>([]);
const selectedMemberRole = ref<TeamRole>("viewer");
const memberBatchActionLoading = ref<"" | "role" | "remove">("");

const pagination = ref({ page: 1, pageSize: 10, total: 0 });
const searchKeyword = ref("");
let memberSearchTimer: ReturnType<typeof setTimeout> | undefined;

const userMap = computed(() => new Map(users.value.map((u) => [u.id, u])));

const memberIds = computed(() => new Set(members.value.map((m) => m.user_id)));

const canManageActiveTeamMembers = computed(() => {
  if (authStore.user?.role === "system_admin") {
    return true;
  }
  const currentUserMember = members.value.find((member) => member.user_id === authStore.user?.id);
  return currentUserMember?.role === "owner" || currentUserMember?.role === "admin";
});

function getMemberDisplayUser(member: TeamMember) {
  return userMap.value.get(member.user_id) ?? {
    id: member.user_id,
    username: member.username || `用户 ${member.user_id}`,
    email: member.email || "",
    full_name: member.full_name || null,
  };
}

/** 成员管理弹窗左侧：所有非当前团队成员的用户（支持搜索过滤） */
const availableMembers = computed(() => {
  const keyword = memberSearchKeyword.value.trim().toLowerCase();
  return users.value.filter((u) => {
    if (memberIds.value.has(u.id)) return false;
    if (!keyword) return true;
    return (
      (u.full_name || "").toLowerCase().includes(keyword) ||
      u.username.toLowerCase().includes(keyword) ||
      u.email.toLowerCase().includes(keyword)
    );
  });
});

const filteredMembers = computed(() => {
  const keyword = currentMemberSearchKeyword.value.trim().toLowerCase();
  return members.value.filter((member) => {
    if (currentMemberRoleFilter.value !== "all" && member.role !== currentMemberRoleFilter.value) {
      return false;
    }
    const memberUser = getMemberDisplayUser(member);
    if (!keyword) return true;
    return (
      (memberUser.full_name || "").toLowerCase().includes(keyword) ||
      memberUser.username.toLowerCase().includes(keyword) ||
      memberUser.email.toLowerCase().includes(keyword) ||
      String(member.user_id).includes(keyword)
    );
  });
});

function mergeUsers(items: AdminUser[]) {
  const merged = new Map(users.value.map((item) => [item.id, item]));
  for (const item of items) {
    merged.set(item.id, item);
  }
  users.value = [...merged.values()];
}

async function loadUserOptions(keyword?: string) {
  userOptionsLoading.value = true;
  try {
    const result = await listUsers({
      page: 1,
      page_size: 100,
      keyword: keyword?.trim() || undefined,
    });
    mergeUsers(result.items);
  } finally {
    userOptionsLoading.value = false;
  }
}

/** 加载团队和用户列表 */
async function loadData() {
  if (loading.value) return;
  loading.value = true;
  loadError.value = null;
  try {
    const teamResult = await listTeams({
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      keyword: searchKeyword.value.trim() || undefined,
    });
    teams.value = teamResult.items;
    pagination.value.total = teamResult.total;
    selectedTeamIds.value = [];
    hasLoadedData.value = true;
  } catch (error) {
    if (hasLoadedData.value) {
      ElMessage.error(error instanceof Error ? error.message : "团队列表刷新失败，请稍后重试");
    } else {
      loadError.value = error;
    }
  } finally {
    loading.value = false;
  }
}

/** 打开新建团队弹窗 */
function openCreateDialog() {
  editingTeam.value = null;
  teamForm.value = { name: "", code: "", description: "" };
  createMemberIds.value = [];
  void loadUserOptions();
  teamDialogVisible.value = true;
}

/** 打开编辑团队弹窗 */
function openEditDialog(team: TeamSummary) {
  editingTeam.value = team;
  teamForm.value = {
    name: team.name,
    code: team.code ?? "",
    description: team.description ?? "",
  };
  teamDialogVisible.value = true;
}

/** 提交团队表单（新建或编辑） */
async function handleTeamSubmit() {
  const { name, code, description } = teamForm.value;
  if (!name.trim()) {
    ElMessage.error("请填写团队名称");
    return;
  }
  teamFormLoading.value = true;
  try {
    const payload = {
      name: name.trim(),
      code: code.trim() || null,
      description: description.trim() || null,
    };
    if (editingTeam.value) {
      const updated = await updateTeam(editingTeam.value.id, payload);
      teams.value = teams.value.map((t) => (t.id === updated.id ? updated : t));
      if (activeTeam.value?.id === updated.id) activeTeam.value = updated;
      ElMessage.success("团队信息已更新");
    } else {
      const created = await createTeam({
        ...payload,
        member_ids: createMemberIds.value,
      });
      teams.value = [created, ...teams.value];
      ElMessage.success("团队已创建");
    }
    teamDialogVisible.value = false;
    await teamScopeStore.bootstrap({ force: true });
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "操作失败");
  } finally {
    teamFormLoading.value = false;
  }
}

/** 删除团队 */
async function handleDeleteTeam(team: TeamSummary) {
  try {
    await ElMessageBox.confirm(
      `即将删除团队「${team.name}」，该操作不可恢复，团队内的成员关系也将一并清除。`,
      "确认删除团队",
      { type: "warning", confirmButtonText: "确认删除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  try {
    await deleteTeam(team.id);
    teams.value = teams.value.filter((t) => t.id !== team.id);
    if (activeTeam.value?.id === team.id) {
      memberDialogVisible.value = false;
      activeTeam.value = null;
    }
    ElMessage.success("团队已删除");
    await teamScopeStore.bootstrap({ force: true });
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "删除失败");
  }
}

function handleTeamSelectionChange(selection: TeamSummary[]) {
  selectedTeamIds.value = selection.map((item) => item.id);
}

async function handleBatchDeleteTeams() {
  if (selectedTeamIds.value.length === 0 || teamBatchActionLoading.value) return;
  try {
    await ElMessageBox.confirm(
      `确定删除已选中的 ${selectedTeamIds.value.length} 个团队吗？团队内成员关系也会一并清除。`,
      "批量删除团队",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }

  teamBatchActionLoading.value = "delete";
  try {
    const result = await bulkActionTeams(selectedTeamIds.value, "delete");
    ElMessage.success(`批量删除完成，影响 ${result.affected} 个团队`);
    await loadData();
    await teamScopeStore.bootstrap({ force: true });
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "批量删除团队失败");
  } finally {
    teamBatchActionLoading.value = "";
  }
}

/** 打开成员管理弹窗 */
async function openMemberPanel(team: TeamSummary) {
  activeTeam.value = team;
  memberLoaded.value = false;
  memberDialogVisible.value = true;
  memberSearchKeyword.value = "";
  currentMemberSearchKeyword.value = "";
  currentMemberRoleFilter.value = "all";
  pendingAddIds.value = [];
  selectedMemberUserIds.value = [];
  selectedMemberRole.value = "viewer";
  try {
    const memberItems = await listTeamMembers(team.id);
    members.value = memberItems;
    mergeUsers(
      memberItems.map((member) => ({
        id: member.user_id,
        username: member.username || `用户 ${member.user_id}`,
        email: member.email || "",
        full_name: member.full_name || null,
        role: "user",
        is_active: true,
        created_at: member.created_at,
        updated_at: member.updated_at,
        team_names: [],
        team_count: 0,
        team_memberships: [],
      })),
    );
  } catch {
    members.value = [];
  } finally {
    memberLoaded.value = true;
  }
}

/** 关闭成员管理弹窗 */
function closeMemberPanel() {
  memberDialogVisible.value = false;
  activeTeam.value = null;
  members.value = [];
  memberLoaded.value = false;
  memberSearchKeyword.value = "";
  currentMemberSearchKeyword.value = "";
  currentMemberRoleFilter.value = "all";
  pendingAddIds.value = [];
  selectedMemberUserIds.value = [];
  selectedMemberRole.value = "viewer";
}

/** 批量添加选中的用户到团队 */
async function handleAddMembers() {
  if (!activeTeam.value || pendingAddIds.value.length === 0) return;
  memberLoading.value = true;
  try {
    const results = await Promise.all(
      pendingAddIds.value.map((uid) =>
        addTeamMember(activeTeam.value!.id, { user_id: uid, role: "viewer" })
      )
    );
    members.value = [...members.value, ...results];
    ElMessage.success(`已添加 ${results.length} 位成员`);
    pendingAddIds.value = [];
    memberSearchKeyword.value = "";
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "添加成员失败");
  } finally {
    memberLoading.value = false;
  }
}

function handleToggleMemberSelection(userId: number, checked: boolean) {
  const selected = new Set(selectedMemberUserIds.value);
  if (checked) {
    selected.add(userId);
  } else {
    selected.delete(userId);
  }
  selectedMemberUserIds.value = [...selected];
}

function handleToggleAllFilteredMembers(checked: boolean) {
  const visibleIds = filteredMembers.value.map((member) => member.user_id);
  if (checked) {
    selectedMemberUserIds.value = [...new Set([...selectedMemberUserIds.value, ...visibleIds])];
    return;
  }
  const visibleSet = new Set(visibleIds);
  selectedMemberUserIds.value = selectedMemberUserIds.value.filter((id) => !visibleSet.has(id));
}

async function handleBatchUpdateMemberRole() {
  if (!activeTeam.value || selectedMemberUserIds.value.length === 0 || memberBatchActionLoading.value) {
    return;
  }
  const roleLabel = TEAM_ROLE_LABELS[selectedMemberRole.value];
  try {
    await ElMessageBox.confirm(
      `确定把已选中的 ${selectedMemberUserIds.value.length} 位成员角色改为「${roleLabel}」吗？`,
      "批量修改角色",
      { type: "info", confirmButtonText: "确定", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }

  memberBatchActionLoading.value = "role";
  try {
    const result = await bulkUpdateTeamMembersRole(
      activeTeam.value.id,
      selectedMemberUserIds.value,
      selectedMemberRole.value,
    );
    members.value = members.value.map((member) =>
      selectedMemberUserIds.value.includes(member.user_id)
        ? { ...member, role: selectedMemberRole.value }
        : member,
    );
    ElMessage.success(`已更新 ${result.affected} 位成员的角色`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "批量修改角色失败");
  } finally {
    memberBatchActionLoading.value = "";
  }
}

async function handleBatchRemoveMembers() {
  if (!activeTeam.value || selectedMemberUserIds.value.length === 0 || memberBatchActionLoading.value) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      `确定从团队中移除已选中的 ${selectedMemberUserIds.value.length} 位成员吗？`,
      "批量移除成员",
      { type: "warning", confirmButtonText: "移除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }

  memberBatchActionLoading.value = "remove";
  try {
    const removingIds = new Set(selectedMemberUserIds.value);
    const result = await bulkDeleteTeamMembers(activeTeam.value.id, selectedMemberUserIds.value);
    members.value = members.value.filter((member) => !removingIds.has(member.user_id));
    selectedMemberUserIds.value = [];
    ElMessage.success(`已移除 ${result.affected} 位成员`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "批量移除成员失败");
  } finally {
    memberBatchActionLoading.value = "";
  }
}

/** 更新成员角色 */
async function handleUpdateRole(member: TeamMember, role: string) {
  if (!activeTeam.value) return;
  updatingMemberId.value = member.id;
  try {
    const updated = await updateTeamMember(activeTeam.value.id, member.user_id, { role: role as TeamRole });
    members.value = members.value.map((m) =>
      m.user_id === updated.user_id && m.team_id === updated.team_id ? updated : m,
    );
    ElMessage.success("成员角色已更新");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "更新角色失败");
  } finally {
    updatingMemberId.value = null;
  }
}

/** 移除成员 */
async function handleRemoveMember(member: TeamMember) {
  if (!activeTeam.value) return;
  const user = userMap.value.get(member.user_id);
  const userName = user?.full_name || user?.username || `用户 #${member.user_id}`;
  try {
    await ElMessageBox.confirm(
      `即将把用户「${userName}」从团队中移除。`,
      "确认移除成员",
      { type: "warning", confirmButtonText: "确认移除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  try {
    await deleteTeamMember(activeTeam.value.id, member.user_id);
    members.value = members.value.filter((m) => m.user_id !== member.user_id);
    selectedMemberUserIds.value = selectedMemberUserIds.value.filter((id) => id !== member.user_id);
    ElMessage.success("成员已移出团队");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "移除失败");
  }
}

/** 搜索团队（重置到第一页） */
function handleSearch() {
  pagination.value.page = 1;
  void loadData();
}

/** 重置搜索条件并刷新 */
function handleResetSearch() {
  searchKeyword.value = "";
  pagination.value.page = 1;
  void loadData();
}

/** 切换每页条数（重置到第一页） */
function handlePageChange(page: number) {
  pagination.value.page = page;
  void loadData();
}

function handleSizeChange(pageSize: number) {
  pagination.value.pageSize = pageSize;
  pagination.value.page = 1;
  void loadData();
}

onMounted(() => {
  void loadData();
});

watch(memberSearchKeyword, (value) => {
  if (memberSearchTimer) {
    clearTimeout(memberSearchTimer);
  }
  memberSearchTimer = setTimeout(() => {
    void loadUserOptions(value);
  }, 300);
});
</script>

<template>
  <section class="team-list-page">
    <AppLoading
      v-if="loading && !hasLoadedData"
      title="团队列表加载中"
      description="正在从后台获取团队数据，请稍候。"
    />

    <AppError
      v-else-if="loadError && !hasLoadedData"
      title="团队列表加载失败"
      description="暂时无法获取团队列表，请稍后重试。"
      :error="loadError"
      @retry="loadData"
    />

    <AdminListPanel v-else>
      <AdminTableToolbar>
        <template #left>
          <el-input
            v-model="searchKeyword"
            placeholder="搜索团队名称或编码…"
            clearable
            :disabled="loading"
            style="width: 280px"
            @clear="handleSearch"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button type="primary" :loading="loading" @click="handleSearch">搜索</el-button>
          <el-button :disabled="loading" @click="handleResetSearch">重置</el-button>
        </template>

        <template #right>
          <AdminBulkActions :selected-count="selectedTeamIds.length">
            <el-button
              link
              type="danger"
              :loading="teamBatchActionLoading === 'delete'"
              :disabled="Boolean(teamBatchActionLoading)"
              @click="handleBatchDeleteTeams"
            >
              删除
            </el-button>
          </AdminBulkActions>
          <span class="team-list-page__stats">
            {{ pagination.total }} 个团队 · {{ users.length }} 个候选账号
          </span>
          <el-button :loading="loading" @click="loadData">
            <el-icon class="mr-2"><Refresh /></el-icon>
            刷新
          </el-button>
          <el-button type="primary" :disabled="loading" @click="openCreateDialog">
            <el-icon class="mr-2"><Plus /></el-icon>
            新建团队
          </el-button>
        </template>
      </AdminTableToolbar>

      <AppEmpty
        v-if="!loading && teams.length === 0"
        class="team-list-page__empty"
        title="还没有团队"
        description="创建第一个团队后，可以把账号分配到具体团队中。"
      >
        <el-button type="primary" :disabled="loading" @click="openCreateDialog">
          <el-icon class="mr-2"><Plus /></el-icon>
          新建团队
        </el-button>
      </AppEmpty>

      <AdminDataTable
        v-else
        :data="teams"
        :loading="loading"
        table-class="team-list-page__table"
        loading-text="正在更新团队列表"
        @selection-change="handleTeamSelectionChange"
      >
        <el-table-column type="selection" width="44" fixed="left" />
        <el-table-column label="团队名称" min-width="220">
          <template #default="{ row }">
            <div class="team-list-page__name-cell">
              <span class="team-list-page__avatar" :style="avatarStyle(row.id)">
                {{ row.name.slice(0, 1) }}
              </span>
              <strong>{{ row.name }}</strong>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="编码" min-width="120">
          <template #default="{ row }">
            <el-tag v-if="row.code" size="small" type="info">{{ row.code }}</el-tag>
            <span v-else class="team-list-page__muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="描述" min-width="200">
          <template #default="{ row }">
            <span class="team-list-page__muted">{{ row.description || "—" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="120">
          <template #default="{ row }">
            <span class="team-list-page__muted">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openMemberPanel(row)">
              <el-icon><User /></el-icon>
              <span>成员</span>
            </el-button>
            <el-button link @click="openEditDialog(row)">
              <el-icon><EditPen /></el-icon>
              <span>编辑</span>
            </el-button>
            <el-button link type="danger" @click="handleDeleteTeam(row)">
              <el-icon><Delete /></el-icon>
              <span>删除</span>
            </el-button>
          </template>
        </el-table-column>
      </AdminDataTable>
      <AdminPagination
        v-if="teams.length > 0"
        :current-page="pagination.page"
        :page-size="pagination.pageSize"
        :total="pagination.total"
        @page-change="handlePageChange"
        @page-size-change="handleSizeChange"
      />
    </AdminListPanel>

    <!-- 新建/编辑团队弹窗 -->
    <AdminDialog
      v-model="teamDialogVisible"
      :title="editingTeam ? '编辑团队' : '新建团队'"
      width="560px"
      :loading="teamFormLoading"
    >
      <el-form label-position="top" @submit.prevent="handleTeamSubmit">
        <el-form-item label="团队名称" required>
          <el-input
            v-model="teamForm.name"
            placeholder="例如 产品部"
            maxlength="100"
          />
        </el-form-item>
        <el-form-item label="团队编码">
          <el-input
            v-model="teamForm.code"
            placeholder="如 PRD"
            maxlength="50"
          />
        </el-form-item>
        <el-form-item label="团队描述">
          <el-input
            v-model="teamForm.description"
            type="textarea"
            placeholder="简要描述团队的职能范围…"
            :rows="3"
          />
        </el-form-item>
        <el-form-item v-if="!editingTeam" label="初始成员">
          <el-select
            v-model="createMemberIds"
            multiple
            filterable
            remote
            reserve-keyword
            :remote-method="loadUserOptions"
            :loading="userOptionsLoading"
            placeholder="搜索并选择成员…"
            style="width: 100%"
          >
            <el-option
              v-for="user in users"
              :key="user.id"
              :label="user.full_name || user.username"
              :value="user.id"
            >
              <div class="team-list-page__select-option">
                <span class="team-list-page__user-avatar-sm" :style="avatarStyle(user.id)">
                  {{ getInitials(user.full_name, user.username) }}
                </span>
                <span class="team-list-page__user-info">
                  <strong>{{ user.full_name || user.username }}</strong>
                  <small>{{ user.email }}</small>
                </span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="teamDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="teamFormLoading" @click="handleTeamSubmit">
          {{ editingTeam ? "保存修改" : "创建团队" }}
        </el-button>
      </template>
    </AdminDialog>

    <!-- 成员管理弹窗 -->
    <AdminDialog
      v-model="memberDialogVisible"
      :title="activeTeam ? `${activeTeam.name} · 成员管理` : '成员管理'"
      width="880px"
      :loading="memberLoading"
      @close="closeMemberPanel"
    >
      <div v-if="!memberLoaded" class="team-list-page__member-panel__loading">
        <el-icon class="is-loading" :size="24" color="#94a3b8"><Search /></el-icon>
        <p>加载成员列表中…</p>
      </div>
      <div v-else class="team-list-page__member-panel">
        <!-- 左侧：添加成员 -->
        <div v-if="canManageActiveTeamMembers" class="team-list-page__member-panel__left">
          <div class="team-list-page__member-panel__header">
            <strong>添加成员</strong>
          </div>
          <div class="team-list-page__member-panel__search">
            <el-input
              v-model="memberSearchKeyword"
              placeholder="搜索姓名、用户名或邮箱…"
              clearable
              size="small"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>
          <div class="team-list-page__member-panel__list">
            <el-checkbox-group v-model="pendingAddIds">
              <div
                v-for="user in availableMembers"
                :key="user.id"
                class="team-list-page__member-panel__user-row"
              >
                <el-checkbox :value="user.id">
                  <div class="team-list-page__member-panel__user-content">
                    <span class="team-list-page__user-avatar-sm" :style="avatarStyle(user.id)">
                      {{ getInitials(user.full_name, user.username) }}
                    </span>
                    <span class="team-list-page__user-info">
                      <strong>{{ user.full_name || user.username }}</strong>
                      <small>{{ user.email }}</small>
                    </span>
                  </div>
                </el-checkbox>
              </div>
            </el-checkbox-group>
            <p v-if="availableMembers.length === 0" class="team-list-page__member-panel__empty">
              没有可添加的用户
            </p>
          </div>
          <div class="team-list-page__member-panel__footer">
            <el-button
              type="primary"
              :disabled="pendingAddIds.length === 0"
              :loading="memberLoading"
              @click="handleAddMembers"
            >
              添加选中 ({{ pendingAddIds.length }})
            </el-button>
          </div>
        </div>

        <!-- 右侧：当前成员 -->
        <div class="team-list-page__member-panel__right">
          <div class="team-list-page__member-panel__header">
            <strong>当前成员 ({{ members.length }})</strong>
            <span v-if="filteredMembers.length !== members.length">
              筛选 {{ filteredMembers.length }}
            </span>
          </div>
          <div class="team-list-page__member-panel__filters">
            <el-input
              v-model="currentMemberSearchKeyword"
              placeholder="搜索当前成员…"
              clearable
              size="small"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-select v-model="currentMemberRoleFilter" size="small" style="width: 104px">
              <el-option value="all" label="全部角色" />
              <el-option
                v-for="opt in TEAM_ROLE_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </div>
          <div v-if="members.length > 0 && canManageActiveTeamMembers" class="team-list-page__member-panel__bulk">
            <el-checkbox
              :model-value="
                filteredMembers.length > 0 &&
                filteredMembers.every((member) => selectedMemberUserIds.includes(member.user_id))
              "
              :indeterminate="
                filteredMembers.some((member) => selectedMemberUserIds.includes(member.user_id)) &&
                !filteredMembers.every((member) => selectedMemberUserIds.includes(member.user_id))
              "
              :disabled="filteredMembers.length === 0"
              @change="(checked) => handleToggleAllFilteredMembers(Boolean(checked))"
            >
              全选当前筛选
            </el-checkbox>
            <AdminBulkActions :selected-count="selectedMemberUserIds.length">
              <el-select
                v-model="selectedMemberRole"
                size="small"
                style="width: 92px"
                :disabled="Boolean(memberBatchActionLoading)"
              >
                <el-option
                  v-for="opt in TEAM_ROLE_OPTIONS"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
              <el-button
                link
                type="primary"
                :loading="memberBatchActionLoading === 'role'"
                :disabled="Boolean(memberBatchActionLoading)"
                @click="handleBatchUpdateMemberRole"
              >
                改角色
              </el-button>
              <el-button
                link
                type="danger"
                :loading="memberBatchActionLoading === 'remove'"
                :disabled="Boolean(memberBatchActionLoading)"
                @click="handleBatchRemoveMembers"
              >
                移除
              </el-button>
            </AdminBulkActions>
          </div>
          <div class="team-list-page__member-panel__list">
            <div v-if="members.length === 0" class="team-list-page__member-panel__empty">
              还没有成员
            </div>
            <div v-else-if="filteredMembers.length === 0" class="team-list-page__member-panel__empty">
              没有匹配的成员
            </div>
            <div
              v-for="member in filteredMembers"
              :key="member.id"
              class="team-list-page__member-panel__user-row"
              :class="{ 'team-list-page__member-panel__user-row--inactive': getMemberDisplayUser(member).is_active === false }"
            >
              <el-checkbox
                :model-value="selectedMemberUserIds.includes(member.user_id)"
                @change="(checked) => handleToggleMemberSelection(member.user_id, Boolean(checked))"
              />
              <span class="team-list-page__member-avatar" :style="avatarStyle(member.user_id)">
                {{ getInitials(getMemberDisplayUser(member).full_name, getMemberDisplayUser(member).username) }}
              </span>
              <div class="team-list-page__member-info">
                <strong>{{ getMemberDisplayUser(member).full_name || getMemberDisplayUser(member).username }}</strong>
                <small>
                  {{ getMemberDisplayUser(member).email || `user_id=${member.user_id}` }}
                  <template v-if="getMemberDisplayUser(member).is_active === false"> · 已停用</template>
                </small>
              </div>
              <div v-if="canManageActiveTeamMembers" class="team-list-page__member-actions">
                <el-select
                  :model-value="member.role"
                  :loading="updatingMemberId === member.id"
                  size="small"
                  style="width: 90px"
                  @change="(role: string) => handleUpdateRole(member, role)"
                >
                  <el-option
                    v-for="opt in TEAM_ROLE_OPTIONS"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
                <el-button link type="danger" size="small" @click="handleRemoveMember(member)">
                  移除
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="memberDialogVisible = false">关闭</el-button>
      </template>
    </AdminDialog>
  </section>
</template>

<style scoped>
.team-list-page {
  --el-color-primary: var(--admin-primary);
  --el-color-primary-light-3: var(--admin-primary-light);
  --el-color-primary-light-5: var(--admin-primary-light);
  --el-color-primary-light-7: var(--admin-primary-border);
  --el-color-primary-light-9: var(--admin-primary-soft);
  --el-color-primary-dark-2: var(--admin-primary-hover);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.team-list-page__stats {
  color: #64748b;
  font-size: 13px;
  white-space: nowrap;
}

.team-list-page__table {
  width: 100%;
}

.team-list-page__empty {
  min-height: 420px;
  border-top: 1px solid #e2e8f0;
}

.team-list-page__name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.team-list-page__name-cell strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.team-list-page__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.team-list-page__muted {
  color: #475569;
  font-size: 13px;
}

/* 成员管理弹窗 */
.team-list-page__member-panel__loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  gap: 12px;
  color: #94a3b8;
  font-size: 13px;
}

.team-list-page__member-panel {
  display: flex;
  gap: 16px;
  min-height: 400px;
}

.team-list-page__member-panel__left,
.team-list-page__member-panel__right {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.team-list-page__member-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 14px;
}

.team-list-page__member-panel__header span {
  color: #64748b;
  font-size: 12px;
  font-weight: 500;
}

.team-list-page__member-panel__search {
  padding: 8px 12px;
  border-bottom: 1px solid #f1f5f9;
}

.team-list-page__member-panel__filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  border-bottom: 1px solid #f1f5f9;
  padding: 8px 12px;
}

.team-list-page__member-panel__bulk {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border-bottom: 1px solid #f1f5f9;
  background: #f8fafc;
  padding: 8px 12px;
}

.team-list-page__member-panel__list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
  max-height: 360px;
}

.team-list-page__member-panel__footer {
  padding: 12px 16px;
  border-top: 1px solid #f1f5f9;
}

.team-list-page__member-panel__user-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}

.team-list-page__member-panel__user-row :deep(.el-checkbox) {
  height: auto;
  margin-right: 0;
}

.team-list-page__member-panel__user-row--inactive {
  opacity: 0.5;
}

.team-list-page__member-panel__user-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.team-list-page__member-panel__empty {
  text-align: center;
  padding: 32px 0;
  color: #94a3b8;
  font-size: 13px;
}

.team-list-page__select-option {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 100%;
}

:deep(.el-select-dropdown__item) {
  height: auto !important;
  padding: 8px 12px !important;
  line-height: normal !important;
}

.team-list-page__user-avatar-sm {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
}

.team-list-page__user-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  line-height: 1.3;
}

.team-list-page__user-info strong {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.team-list-page__user-info small {
  font-size: 11px;
  color: #94a3b8;
}

.team-list-page__member-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.team-list-page__member-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.team-list-page__member-info strong {
  font-size: 13px;
  font-weight: 500;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.team-list-page__member-info small {
  font-size: 11px;
  color: #94a3b8;
}

.team-list-page__member-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

@media (max-width: 960px) {
  .team-list-page__member-panel {
    flex-direction: column;
  }

  .team-list-page__member-panel__list {
    max-height: 280px;
  }
}
</style>
