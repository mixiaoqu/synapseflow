<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Delete,
  EditPen,
  Key,
  Plus,
  Refresh,
  Search,
  View,
} from "@element-plus/icons-vue";

import AdminBulkActions from "@/app/components/admin/AdminBulkActions.vue";
import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import { bulkActionUsers, createUser, deleteUser, getUser, listUsers, updateUser } from "@/shared/api/users";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import {
  ROLE_LABELS,
  ROLE_OPTIONS,
  ROLE_TAG_TYPES,
} from "@/shared/types/user";
import { TEAM_ROLE_LABELS } from "@/shared/types/team";
import type { AdminUser, CreateUserPayload, UpdateUserPayload } from "@/shared/types/user";

const AVATAR_PALETTES = [
  "background:#eff6ff;color:#1d4ed8;border-color:#bfdbfe",
  "background:#ecfeff;color:#0e7490;border-color:#a5f3fc",
  "background:#ecfdf5;color:#047857;border-color:#bbf7d0",
  "background:#f5f3ff;color:#6d28d9;border-color:#ddd6fe",
  "background:#fff7ed;color:#c2410c;border-color:#fed7aa",
  "background:#f1f5f9;color:#334155;border-color:#cbd5e1",
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
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

const STATUS_OPTIONS = [
  { value: "all", label: "全部状态" },
  { value: "active", label: "启用中" },
  { value: "inactive", label: "已停用" },
] as const;

const USERNAME_MIN_LENGTH = 3;
const PASSWORD_MIN_LENGTH = 8;
const EMAIL_MIN_LENGTH = 5;
const FULL_NAME_MAX_LENGTH = 100;

const users = ref<AdminUser[]>([]);
const loading = ref(false);
const loadError = ref<unknown>(null);
const hasLoadedData = ref(false);
const selectedUserIds = ref<number[]>([]);
const batchActionLoading = ref<"" | "enable" | "disable" | "delete">("");

const searchKeyword = ref("");
const roleFilter = ref("all");
const statusFilter = ref("all");

const pagination = ref({ page: 1, pageSize: 10, total: 0 });

const createDialogVisible = ref(false);
const createLoading = ref(false);
const createForm = ref({
  username: "",
  email: "",
  full_name: "",
  password: "",
  role: "end_user",
  is_active: true,
});

const editDialogVisible = ref(false);
const editLoading = ref(false);
const editItem = ref<AdminUser | null>(null);
const editForm = ref({
  username: "",
  full_name: "",
  email: "",
  role: "end_user",
  is_active: true,
});

const detailDialogVisible = ref(false);
const detailLoading = ref(false);
const detailItem = ref<AdminUser | null>(null);

const resetPasswordDialogVisible = ref(false);
const resetPasswordLoading = ref(false);
const resetPasswordItem = ref<AdminUser | null>(null);
const resetPasswordForm = ref({ password: "" });

const savingId = ref<number | null>(null);

/** 加载用户列表 */
async function loadData() {
  if (loading.value) return;
  loading.value = true;
  loadError.value = null;
  try {
    const result = await listUsers({
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      keyword: searchKeyword.value.trim() || undefined,
      role: roleFilter.value === "all" ? undefined : roleFilter.value,
      is_active:
        statusFilter.value === "all"
          ? undefined
          : statusFilter.value === "active",
    });
    users.value = result.items;
    pagination.value.total = result.total;
    selectedUserIds.value = [];
    hasLoadedData.value = true;
  } catch (error) {
    if (hasLoadedData.value) {
      ElMessage.error(error instanceof Error ? error.message : "用户列表刷新失败，请稍后重试");
    } else {
      loadError.value = error;
    }
  } finally {
    loading.value = false;
  }
}

/** 打开新建用户弹窗 */
function openCreateDialog() {
  createForm.value = {
    username: "",
    email: "",
    full_name: "",
    password: "",
    role: "end_user",
    is_active: true,
  };
  createDialogVisible.value = true;
}

/** 提交新建用户 */
async function handleCreate() {
  const { username, email, full_name, password, role, is_active } = createForm.value;
  if (!username.trim() || !email.trim() || !password.trim()) {
    ElMessage.error("请先填写用户名、邮箱和初始密码");
    return;
  }
  if (username.trim().length < USERNAME_MIN_LENGTH) {
    ElMessage.error(`用户名至少需要 ${USERNAME_MIN_LENGTH} 个字符`);
    return;
  }
  if (email.trim().length < EMAIL_MIN_LENGTH) {
    ElMessage.error("请输入有效的邮箱地址");
    return;
  }
  if (password.length < PASSWORD_MIN_LENGTH) {
    ElMessage.error(`初始密码至少需要 ${PASSWORD_MIN_LENGTH} 位`);
    return;
  }
  if (full_name.trim().length > FULL_NAME_MAX_LENGTH) {
    ElMessage.error(`姓名不能超过 ${FULL_NAME_MAX_LENGTH} 个字符`);
    return;
  }
  createLoading.value = true;
  try {
    const payload: CreateUserPayload = {
      username: username.trim(),
      email: email.trim(),
      password,
      full_name: full_name.trim() || null,
      role,
      is_active,
    };
    const created = await createUser(payload);
    users.value = [created, ...users.value];
    createDialogVisible.value = false;
    ElMessage.success("用户已创建");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "创建用户失败");
  } finally {
    createLoading.value = false;
  }
}

/** 打开编辑用户弹窗 */
function openEditDialog(user: AdminUser) {
  editItem.value = user;
  editForm.value = {
    username: user.username,
    full_name: user.full_name ?? "",
    email: user.email,
    role: user.role,
    is_active: user.is_active,
  };
  editDialogVisible.value = true;
}

/** 打开用户详情弹窗 */
async function openDetailDialog(user: AdminUser) {
  detailDialogVisible.value = true;
  detailItem.value = user;
  detailLoading.value = true;
  try {
    detailItem.value = await getUser(user.id);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "获取用户详情失败");
  } finally {
    detailLoading.value = false;
  }
}

/** 打开重置密码弹窗 */
function openResetPasswordDialog(user: AdminUser) {
  resetPasswordItem.value = user;
  resetPasswordForm.value = { password: "" };
  resetPasswordDialogVisible.value = true;
}

/** 提交编辑用户 */
async function handleEditSubmit() {
  if (!editItem.value) return;
  const { username, full_name, email, role, is_active } = editForm.value;
  if (username.trim().length < USERNAME_MIN_LENGTH) {
    ElMessage.error(`用户名至少需要 ${USERNAME_MIN_LENGTH} 个字符`);
    return;
  }
  if (email.trim().length < EMAIL_MIN_LENGTH) {
    ElMessage.error("请输入有效的邮箱地址");
    return;
  }
  if (full_name.trim().length > FULL_NAME_MAX_LENGTH) {
    ElMessage.error(`姓名不能超过 ${FULL_NAME_MAX_LENGTH} 个字符`);
    return;
  }
  editLoading.value = true;
  try {
    const payload: UpdateUserPayload = {
      username: username.trim(),
      full_name: full_name.trim() || null,
      email: email.trim(),
      role,
      is_active,
    };
    const updated = await updateUser(editItem.value.id, payload);
    users.value = users.value.map((u) => (u.id === updated.id ? updated : u));
    editDialogVisible.value = false;
    ElMessage.success("用户信息已更新");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "更新用户失败");
  } finally {
    editLoading.value = false;
  }
}

/** 提交重置密码 */
async function handleResetPasswordSubmit() {
  if (!resetPasswordItem.value) return;
  const password = resetPasswordForm.value.password;
  if (password.length < PASSWORD_MIN_LENGTH) {
    ElMessage.error(`新密码至少需要 ${PASSWORD_MIN_LENGTH} 位`);
    return;
  }

  resetPasswordLoading.value = true;
  try {
    await updateUser(resetPasswordItem.value.id, { password });
    resetPasswordDialogVisible.value = false;
    ElMessage.success("密码已重置");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "重置密码失败");
  } finally {
    resetPasswordLoading.value = false;
  }
}

/** 快速切换用户启用/停用状态 */
async function handleToggleStatus(user: AdminUser) {
  const actionText = user.is_active ? "停用" : "启用";
  try {
    await ElMessageBox.confirm(
      `确定${actionText}账号「${user.full_name || user.username}」吗？`,
      `${actionText}账号`,
      {
        type: user.is_active ? "warning" : "info",
        confirmButtonText: actionText,
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  savingId.value = user.id;
  try {
    const updated = await updateUser(user.id, { is_active: !user.is_active });
    users.value = users.value.map((u) => (u.id === updated.id ? updated : u));
    ElMessage.success(updated.is_active ? "账号已启用" : "账号已停用");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "操作失败");
  } finally {
    savingId.value = null;
  }
}

function handleSelectionChange(selection: AdminUser[]) {
  selectedUserIds.value = selection.map((item) => item.id);
}

async function handleDeleteUser(user: AdminUser) {
  try {
    await ElMessageBox.confirm(
      `确定删除账号「${user.full_name || user.username}」吗？删除后该账号将无法登录，但历史数据会保留。`,
      "删除用户",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  try {
    await deleteUser(user.id);
    ElMessage.success("用户已删除");
    await loadData();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "删除用户失败");
  }
}

async function handleBatchAction(action: "enable" | "disable" | "delete") {
  if (selectedUserIds.value.length === 0 || batchActionLoading.value) return;
  const actionTextMap = {
    enable: "批量启用",
    disable: "批量停用",
    delete: "批量删除",
  };
  const actionText = actionTextMap[action];
  try {
    await ElMessageBox.confirm(
      `确定${actionText}已选中的 ${selectedUserIds.value.length} 个用户吗？`,
      actionText,
      {
        type: action === "delete" ? "warning" : "info",
        confirmButtonText: action === "delete" ? "删除" : "确定",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  batchActionLoading.value = action;
  try {
    const result = await bulkActionUsers(selectedUserIds.value, action);
    ElMessage.success(`${actionText}完成，影响 ${result.affected} 个用户`);
    await loadData();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : `${actionText}失败`);
  } finally {
    batchActionLoading.value = "";
  }
}

/** 搜索用户（重置到第一页） */
function handleSearch() {
  pagination.value.page = 1;
  void loadData();
}

/** 重置搜索条件并刷新 */
function handleResetSearch() {
  searchKeyword.value = "";
  roleFilter.value = "all";
  statusFilter.value = "all";
  pagination.value.page = 1;
  void loadData();
}

/** 切换每页条数（重置到第一页） */
function handleSizeChange() {
  pagination.value.page = 1;
  void loadData();
}

onMounted(() => {
  void loadData();
});
</script>

<template>
  <section class="user-list-page">
    <AppLoading
      v-if="loading && !hasLoadedData"
      title="用户列表加载中"
      description="正在从后台获取用户数据，请稍候。"
    />

    <AppError
      v-else-if="loadError && !hasLoadedData"
      title="用户列表加载失败"
      description="暂时无法获取用户列表，请稍后重试。"
      :error="loadError"
      @retry="loadData"
    />

    <AdminListPanel v-else>
      <AdminTableToolbar>
        <template #left>
          <el-input
            v-model="searchKeyword"
            placeholder="搜索用户名、姓名或邮箱…"
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
          <el-select
            v-model="roleFilter"
            :disabled="loading"
            style="width: 150px"
            @change="handleSearch"
          >
            <el-option value="all" label="全部角色" />
            <el-option
              v-for="opt in ROLE_OPTIONS"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
            />
          </el-select>
          <el-select
            v-model="statusFilter"
            :disabled="loading"
            style="width: 130px"
            @change="handleSearch"
          >
            <el-option
              v-for="opt in STATUS_OPTIONS"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
            />
          </el-select>
        </template>

        <template #right>
          <AdminBulkActions :selected-count="selectedUserIds.length">
            <el-button
              link
              type="primary"
              :loading="batchActionLoading === 'enable'"
              :disabled="Boolean(batchActionLoading)"
              @click="handleBatchAction('enable')"
            >
              启用
            </el-button>
            <el-button
              link
              type="primary"
              :loading="batchActionLoading === 'disable'"
              :disabled="Boolean(batchActionLoading)"
              @click="handleBatchAction('disable')"
            >
              停用
            </el-button>
            <el-button
              link
              type="danger"
              :loading="batchActionLoading === 'delete'"
              :disabled="Boolean(batchActionLoading)"
              @click="handleBatchAction('delete')"
            >
              删除
            </el-button>
          </AdminBulkActions>
          <el-button :loading="loading" @click="loadData">
            <el-icon class="mr-2"><Refresh /></el-icon>
            刷新
          </el-button>
          <el-button type="primary" :disabled="loading" @click="openCreateDialog">
            <el-icon class="mr-2"><Plus /></el-icon>
            新建用户
          </el-button>
        </template>
      </AdminTableToolbar>

      <AppEmpty
        v-if="!loading && users.length === 0"
        class="user-list-page__empty"
        title="还没有用户"
        description="创建第一个用户后，可以在这里管理账号信息、角色权限和启停状态。"
      >
        <el-button type="primary" :disabled="loading" @click="openCreateDialog">
          <el-icon class="mr-2"><Plus /></el-icon>
          新建用户
        </el-button>
      </AppEmpty>

      <el-table
        v-else
        v-loading="loading"
        :data="users"
        row-key="id"
        class="user-list-page__table"
        height="calc(100vh - 260px)"
        element-loading-text="正在更新用户列表"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="44" fixed="left" />
        <el-table-column label="用户" min-width="240">
          <template #default="{ row }">
            <div class="user-list-page__user-cell">
              <span class="user-list-page__avatar" :style="avatarStyle(row.id)">
                {{ getInitials(row.full_name, row.username) }}
              </span>
              <div class="user-list-page__user-info">
                <strong>{{ row.full_name || row.username }}</strong>
                <small>@{{ row.username }} · {{ row.email }}</small>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="角色" min-width="120">
          <template #default="{ row }">
            <el-tag :type="(ROLE_TAG_TYPES[row.role] as any) || 'info'" size="small">
              {{ ROLE_LABELS[row.role] ?? row.role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="所属团队" min-width="180">
          <template #default="{ row }">
            <span v-if="!row.team_count" class="user-list-page__muted">未加入团队</span>
            <el-tooltip
              v-else
              effect="dark"
              placement="top"
              :content="(row.team_names || []).join('、')"
            >
              <span class="user-list-page__team-summary">
                {{ (row.team_names || []).slice(0, 2).join("、") }}
                <template v-if="(row.team_count || 0) > 2">等 {{ row.team_count }} 个团队</template>
              </span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              :loading="savingId === row.id"
              inline-prompt
              active-text="启用"
              inactive-text="停用"
              @change="handleToggleStatus(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="160">
          <template #default="{ row }">
            <span class="user-list-page__muted">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="152" fixed="right" align="center">
          <template #default="{ row }">
            <div class="user-list-page__row-actions">
              <el-button link type="primary" title="查看详情" @click="openDetailDialog(row)">
                <el-icon><View /></el-icon>
              </el-button>
              <el-button link type="primary" title="编辑用户" @click="openEditDialog(row)">
                <el-icon><EditPen /></el-icon>
              </el-button>
              <el-button link type="primary" title="重置密码" @click="openResetPasswordDialog(row)">
                <el-icon><Key /></el-icon>
              </el-button>
              <el-button link type="danger" title="删除用户" @click="handleDeleteUser(row)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="users.length > 0" class="user-list-page__pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadData"
          @size-change="handleSizeChange"
        />
      </div>
    </AdminListPanel>

    <!-- 新建用户弹窗 -->
    <el-dialog
      v-model="createDialogVisible"
      title="新建用户"
      width="520px"
      class="user-list-page__dialog"
      :close-on-click-modal="false"
    >
      <el-form label-position="top" @submit.prevent="handleCreate">
        <div class="user-list-page__form-row">
          <el-form-item label="用户名" required>
            <el-input
              v-model="createForm.username"
              placeholder="如 zhangsan"
              :minlength="USERNAME_MIN_LENGTH"
            />
          </el-form-item>
          <el-form-item label="姓名">
            <el-input
              v-model="createForm.full_name"
              placeholder="如 张三"
              :maxlength="FULL_NAME_MAX_LENGTH"
            />
          </el-form-item>
        </div>
        <el-form-item label="邮箱" required>
          <el-input
            v-model="createForm.email"
            type="email"
            placeholder="user@example.com"
          />
        </el-form-item>
        <div class="user-list-page__form-row">
          <el-form-item label="初始密码" required>
            <el-input
              v-model="createForm.password"
              type="password"
              show-password
              :placeholder="`至少 ${PASSWORD_MIN_LENGTH} 位`"
            />
          </el-form-item>
          <el-form-item label="角色">
            <el-select v-model="createForm.role" style="width: 100%">
              <el-option
                v-for="opt in ROLE_OPTIONS"
                :key="opt.value"
                :value="opt.value"
                :label="opt.label"
              />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="启用状态">
          <el-switch
            v-model="createForm.is_active"
            active-text="创建后立即启用账号"
            style="--el-switch-on-color: #10b981"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="handleCreate">
          创建用户
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑用户弹窗 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑用户"
      width="520px"
      class="user-list-page__dialog"
      :close-on-click-modal="false"
    >
      <div v-if="editItem" class="user-list-page__edit-header">
        <span class="user-list-page__avatar" :style="avatarStyle(editItem.id)">
          {{ getInitials(editItem.full_name, editItem.username) }}
        </span>
        <div>
          <p class="user-list-page__edit-name">{{ editItem.full_name || editItem.username }}</p>
          <p class="user-list-page__edit-username">@{{ editItem.username }}</p>
        </div>
      </div>
      <el-form label-position="top" @submit.prevent="handleEditSubmit">
        <el-form-item label="用户名" required>
          <el-input
            v-model="editForm.username"
            :minlength="USERNAME_MIN_LENGTH"
            maxlength="50"
            placeholder="用户名"
          />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input
            v-model="editForm.full_name"
            :maxlength="FULL_NAME_MAX_LENGTH"
            placeholder="姓名"
          />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input
            v-model="editForm.email"
            type="email"
            placeholder="邮箱"
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.role" style="width: 100%">
            <el-option
              v-for="opt in ROLE_OPTIONS"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch
            v-model="editForm.is_active"
            :active-text="editForm.is_active ? '账号已启用' : '账号已停用'"
            style="--el-switch-on-color: #10b981"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="handleEditSubmit">
          保存修改
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="detailDialogVisible"
      title="用户详情"
      width="520px"
      class="user-list-page__dialog"
      :close-on-click-modal="false"
    >
      <div v-loading="detailLoading" class="user-list-page__detail">
        <template v-if="detailItem">
          <div class="user-list-page__edit-header">
            <span class="user-list-page__avatar" :style="avatarStyle(detailItem.id)">
              {{ getInitials(detailItem.full_name, detailItem.username) }}
            </span>
            <div>
              <p class="user-list-page__edit-name">{{ detailItem.full_name || detailItem.username }}</p>
              <p class="user-list-page__edit-username">@{{ detailItem.username }}</p>
            </div>
          </div>
          <dl class="user-list-page__detail-list">
            <div>
              <dt>邮箱</dt>
              <dd>{{ detailItem.email }}</dd>
            </div>
            <div>
              <dt>角色</dt>
              <dd>{{ ROLE_LABELS[detailItem.role] ?? detailItem.role }}</dd>
            </div>
            <div>
              <dt>状态</dt>
              <dd>{{ detailItem.is_active ? "启用中" : "已停用" }}</dd>
            </div>
            <div>
              <dt>所属团队</dt>
              <dd>
                <div class="user-list-page__detail-teams">
                  <div
                    v-for="membership in detailItem.team_memberships || []"
                    :key="membership.team_id"
                    class="user-list-page__detail-team"
                  >
                    <span>
                      {{ membership.team_name }}
                      <small>{{ TEAM_ROLE_LABELS[membership.role] || membership.role }}</small>
                    </span>
                  </div>
                  <span
                    v-if="!detailItem.team_memberships || detailItem.team_memberships.length === 0"
                    class="user-list-page__muted"
                  >
                    未加入团队
                  </span>
                </div>
              </dd>
            </div>
            <div>
              <dt>创建时间</dt>
              <dd>{{ formatDate(detailItem.created_at) }}</dd>
            </div>
            <div>
              <dt>更新时间</dt>
              <dd>{{ formatDate(detailItem.updated_at) }}</dd>
            </div>
          </dl>
        </template>
      </div>
    </el-dialog>

    <el-dialog
      v-model="resetPasswordDialogVisible"
      title="重置密码"
      width="460px"
      class="user-list-page__dialog"
      :close-on-click-modal="false"
    >
      <div v-if="resetPasswordItem" class="user-list-page__edit-header">
        <span class="user-list-page__avatar" :style="avatarStyle(resetPasswordItem.id)">
          {{ getInitials(resetPasswordItem.full_name, resetPasswordItem.username) }}
        </span>
        <div>
          <p class="user-list-page__edit-name">
            {{ resetPasswordItem.full_name || resetPasswordItem.username }}
          </p>
          <p class="user-list-page__edit-username">@{{ resetPasswordItem.username }}</p>
        </div>
      </div>

      <el-form label-position="top" @submit.prevent="handleResetPasswordSubmit">
        <el-form-item label="新密码" required>
          <el-input
            v-model="resetPasswordForm.password"
            type="password"
            show-password
            :minlength="PASSWORD_MIN_LENGTH"
            :placeholder="`至少 ${PASSWORD_MIN_LENGTH} 位`"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="resetPasswordDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="resetPasswordLoading"
          @click="handleResetPasswordSubmit"
        >
          确认重置
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.user-list-page {
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

.user-list-page__table {
  width: 100%;
}

.user-list-page__empty {
  min-height: 420px;
  border-top: 1px solid #e2e8f0;
}

.user-list-page__user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.user-list-page__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.user-list-page__user-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.user-list-page__user-info strong {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-list-page__user-info small {
  font-size: 12px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-list-page__muted {
  color: #475569;
  font-size: 13px;
}

.user-list-page__team-summary {
  display: inline-block;
  max-width: 160px;
  overflow: hidden;
  color: #334155;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}

.user-list-page__row-actions {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
}

.user-list-page__detail {
  min-height: 220px;
}

:deep(.user-list-page__dialog.el-dialog) {
  overflow: hidden;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  box-shadow: 0 20px 48px rgba(15, 23, 42, 0.18);
}

:deep(.user-list-page__dialog .el-dialog__header) {
  display: flex;
  align-items: center;
  min-height: 54px;
  margin: 0;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 0 18px;
}

:deep(.user-list-page__dialog .el-dialog__title) {
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
}

:deep(.user-list-page__dialog .el-dialog__headerbtn) {
  top: 0;
  right: 10px;
  width: 36px;
  height: 54px;
}

:deep(.user-list-page__dialog .el-dialog__body) {
  padding: 18px;
}

:deep(.user-list-page__dialog .el-dialog__footer) {
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
  padding: 12px 18px;
}

:deep(.user-list-page__dialog .el-form-item) {
  margin-bottom: 16px;
}

:deep(.user-list-page__dialog .el-form-item__label) {
  color: #475569;
  font-size: 13px;
  font-weight: 600;
}

:deep(.user-list-page__dialog .el-input__wrapper),
:deep(.user-list-page__dialog .el-select__wrapper),
:deep(.user-list-page__dialog .el-textarea__inner) {
  border-radius: 7px;
  box-shadow: 0 0 0 1px #cbd5e1 inset;
}

:deep(.user-list-page__dialog .el-input__wrapper:hover),
:deep(.user-list-page__dialog .el-select__wrapper:hover),
:deep(.user-list-page__dialog .el-textarea__inner:hover) {
  box-shadow: 0 0 0 1px #94a3b8 inset;
}

:deep(.user-list-page__dialog .el-input__wrapper.is-focus),
:deep(.user-list-page__dialog .el-select__wrapper.is-focused),
:deep(.user-list-page__dialog .el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px var(--admin-primary) inset;
}

.user-list-page__detail-list {
  display: grid;
  gap: 12px;
  margin: 0;
}

.user-list-page__detail-list > div {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: 12px;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 12px;
}

.user-list-page__detail-list dt {
  color: #64748b;
  font-size: 13px;
}

.user-list-page__detail-list dd {
  min-width: 0;
  margin: 0;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.user-list-page__detail-teams {
  display: grid;
  gap: 8px;
}

.user-list-page__detail-team {
  display: flex;
  align-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 7px 10px;
}

.user-list-page__detail-team span {
  min-width: 0;
  color: #0f172a;
  font-weight: 600;
}

.user-list-page__detail-team small {
  margin-left: 6px;
  color: #64748b;
  font-size: 12px;
  font-weight: 500;
}

.user-list-page__pagination {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
  padding: 12px;
}

/* 弹窗表单 */
.user-list-page__form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}

.user-list-page__edit-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.user-list-page__edit-name {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}

.user-list-page__edit-username {
  margin: 2px 0 0;
  font-size: 12px;
  color: #94a3b8;
}

@media (max-width: 768px) {
  .user-list-page__form-row {
    grid-template-columns: 1fr;
  }
}
</style>
