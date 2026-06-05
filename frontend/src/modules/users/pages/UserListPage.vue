<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  EditPen,
  Plus,
  Search,
} from "@element-plus/icons-vue";

import { createUser, listUsers, updateUser } from "@/shared/api/users";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import {
  ROLE_LABELS,
  ROLE_OPTIONS,
  ROLE_TAG_TYPES,
} from "@/shared/types/user";
import type { AdminUser, CreateUserPayload, UpdateUserPayload } from "@/shared/types/user";

const AVATAR_PALETTES = [
  "background:#eff6ff;color:#1d4ed8",
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

const searchKeyword = ref("");
const roleFilter = ref("all");
const statusFilter = ref("all");

const pagination = ref({ page: 1, pageSize: 20, total: 0 });

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
  full_name: "",
  email: "",
  role: "end_user",
  is_active: true,
});

const savingId = ref<number | null>(null);

/** 前端过滤后的用户列表（仅角色和状态，关键词走后端） */
const filteredUsers = computed(() => {
  return users.value.filter((item) => {
    const matchesRole = roleFilter.value === "all" || item.role === roleFilter.value;
    const matchesStatus =
      statusFilter.value === "all" ||
      (statusFilter.value === "active" ? item.is_active : !item.is_active);
    return matchesRole && matchesStatus;
  });
});

/** 是否有筛选条件 */
const activeFilters = computed(
  () =>
    searchKeyword.value.trim() !== "" ||
    roleFilter.value !== "all" ||
    statusFilter.value !== "all",
);

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
    });
    users.value = result.items;
    pagination.value.total = result.total;
  } catch (error) {
    loadError.value = error;
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
    full_name: user.full_name ?? "",
    email: user.email,
    role: user.role,
    is_active: user.is_active,
  };
  editDialogVisible.value = true;
}

/** 提交编辑用户 */
async function handleEditSubmit() {
  if (!editItem.value) return;
  const { full_name, email, role, is_active } = editForm.value;
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

/** 快速切换用户启用/停用状态 */
async function handleToggleStatus(user: AdminUser) {
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

/** 清除筛选条件并重新加载 */
function handleClearFilters() {
  searchKeyword.value = "";
  roleFilter.value = "all";
  statusFilter.value = "all";
  pagination.value.page = 1;
  void loadData();
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
    <header class="user-list-page__header">
      <div class="user-list-page__header-copy">
        <h1 class="user-list-page__title">用户管理</h1>
        <p class="user-list-page__description">
          管理系统中所有用户的账号信息、角色权限和启停状态。
        </p>
      </div>
      <div class="user-list-page__header-actions">
        <el-button type="primary" @click="openCreateDialog">
          <el-icon class="mr-2"><Plus /></el-icon>
          新建用户
        </el-button>
      </div>
    </header>

    <AppLoading
      v-if="loading"
      title="用户列表加载中"
      description="正在从后台获取用户数据，请稍候。"
    />

    <AppError
      v-else-if="loadError"
      title="用户列表加载失败"
      description="暂时无法获取用户列表，请稍后重试。"
      :error="loadError"
      @retry="loadData"
    />

    <AppEmpty
      v-else-if="users.length === 0"
      title="还没有用户"
      description="点击上方「新建用户」来添加第一个用户。"
    />

    <section v-else class="user-list-page__table-panel">
      <!-- 筛选栏 -->
      <div class="user-list-page__toolbar">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索用户名、姓名或邮箱…"
          clearable
          style="width: 280px"
          @clear="handleSearch"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" @click="handleSearch">搜索</el-button>
        <el-button @click="handleResetSearch">重置</el-button>
        <el-select v-model="roleFilter" style="width: 150px">
          <el-option value="all" label="全部角色" />
          <el-option
            v-for="opt in ROLE_OPTIONS"
            :key="opt.value"
            :value="opt.value"
            :label="opt.label"
          />
        </el-select>
        <el-select v-model="statusFilter" style="width: 130px">
          <el-option
            v-for="opt in STATUS_OPTIONS"
            :key="opt.value"
            :value="opt.value"
            :label="opt.label"
          />
        </el-select>
      </div>

      <!-- 用户表格 -->
      <el-table :data="filteredUsers" row-key="id" class="user-list-page__table">
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
        <el-table-column label="操作" width="80" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEditDialog(row)">
              <el-icon><EditPen /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="user-list-page__pagination">
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
    </section>

    <!-- 新建用户弹窗 -->
    <el-dialog
      v-model="createDialogVisible"
      title="新建用户"
      width="520px"
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
  </section>
</template>

<style scoped>
.user-list-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.user-list-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 56px;
  border: 1px solid #dbe2ea;
  border-radius: 12px;
  background: #ffffff;
  padding: 16px 18px;
}

.user-list-page__header-copy {
  min-width: 0;
}

.user-list-page__title {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}

.user-list-page__description {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.user-list-page__header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 表格面板 */
.user-list-page__table-panel {
  border: 1px solid #dbe2ea;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
  padding: 8px 8px 2px;
}

.user-list-page__toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px 12px;
  flex-wrap: wrap;
}

.user-list-page__table {
  width: 100%;
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
  border-radius: 50%;
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
  font-weight: 500;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-list-page__user-info small {
  font-size: 12px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-list-page__muted {
  color: #64748b;
  font-size: 13px;
}

.user-list-page__pagination {
  display: flex;
  justify-content: flex-end;
  padding: 12px 12px 16px;
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
  .user-list-page__header {
    flex-direction: column;
    align-items: stretch;
  }

  .user-list-page__header-actions {
    justify-content: flex-end;
  }

  .user-list-page__form-row {
    grid-template-columns: 1fr;
  }
}
</style>
