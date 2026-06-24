<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  ArrowRight,
  CirclePlus,
  Delete,
  Document,
  EditPen,
  Folder,
  MoreFilled,
  RefreshRight,
  Search,
  InfoFilled,
  UploadFilled,
  View,
} from "@element-plus/icons-vue";

import AdminBulkActions from "@/app/components/admin/AdminBulkActions.vue";
import AdminDataTable from "@/app/components/admin/AdminDataTable.vue";
import AdminDialog from "@/app/components/admin/AdminDialog.vue";
import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminPagination from "@/app/components/admin/AdminPagination.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import {
  createDocumentCategory,
  deleteDocumentCategory,
  listDocumentCategoriesTree,
  updateDocumentCategory,
} from "@/shared/api/document-categories";
import {
  deleteDocument,
  deleteDocumentsBatch,
  indexDocument,
  listDocuments,
  publishDocumentsBatch,
  publishDocumentsByFilter,
  rejectDocumentsBatch,
  submitDocumentsForReviewBatch,
  submitDocumentsForReviewByFilter,
  uploadDocumentsBatch,
  unpublishDocumentsBatch,
} from "@/shared/api/documents";
import {
  getKnowledgeBase,
  reindexKnowledgeBaseDocuments,
} from "@/shared/api/knowledge-bases";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import StatusTag from "@/shared/components/page/StatusTag.vue";
import { useAdminBreadcrumbStore } from "@/stores/admin-breadcrumb";
import { useTeamScopeStore } from "@/stores/team-scope";
import { isForbiddenError } from "@/shared/utils/error";
import type {
  DocumentCategoryTreeNode,
} from "@/shared/types/document-category";
import type {
  DocumentLifecycleStatus,
  DocumentSummary,
} from "@/shared/types/document";
import type { KnowledgeBaseSummary } from "@/shared/types/knowledge-base";

type CategoryFilterKey = "all" | number;

interface CategoryTreeListItem {
  node: DocumentCategoryTreeNode;
  depth: number;
  path: string;
  hasChildren: boolean;
}

interface CategorySelectOption {
  id: number;
  depth: number;
  label: string;
  path: string;
  node: DocumentCategoryTreeNode;
}

interface DocumentStatusTabItem {
  label: string;
  value: "" | DocumentLifecycleStatus;
  count: number | null;
}

type UploadTargetCategoryValue = "uncategorized" | number;

interface UploadQueueItem {
  raw: File;
  name: string;
  path: string;
  category: string;
  isNewCategory: boolean;
  size: number;
}

interface UploadInputFile extends File {
  customPath?: string;
}

interface FileSystemEntryLike {
  isFile: boolean;
  isDirectory: boolean;
  name: string;
  file?: (callback: (file: File) => void) => void;
  createReader?: () => {
    readEntries: (callback: (entries: FileSystemEntryLike[]) => void) => void;
  };
}

const route = useRoute();
const router = useRouter();
const adminBreadcrumbStore = useAdminBreadcrumbStore();
const teamScopeStore = useTeamScopeStore();

const knowledgeBase = ref<KnowledgeBaseSummary | null>(null);
const categories = ref<DocumentCategoryTreeNode[]>([]);
const expandedCategoryIds = ref<Set<number>>(new Set());
const documents = ref<DocumentSummary[]>([]);
const documentStatusCounts = ref<Record<string, number>>({});
const pageLoading = ref(false);
const documentsLoading = ref(false);
const loadError = ref<unknown>(null);
const categoryActionLoading = ref(false);
const documentActionLoading = ref(false);
const uploadLoading = ref(false);
const selectedCategoryKey = ref<CategoryFilterKey>("all");
const selectedDocuments = ref<DocumentSummary[]>([]);
const fileInputRef = ref<HTMLInputElement | null>(null);
const folderInputRef = ref<HTMLInputElement | null>(null);
const uploadDialogVisible = ref(false);
const detailDrawerVisible = ref(false);
const uploadTargetCategory = ref<UploadTargetCategoryValue>("uncategorized");
const uploadQueue = ref<UploadQueueItem[]>([]);
const uploadDragging = ref(false);

const documentQuery = reactive({
  keyword: "",
  status: "" as "" | DocumentLifecycleStatus,
  page: 1,
  pageSize: 10,
  total: 0,
});

function flattenCategoryTree(nodes: DocumentCategoryTreeNode[]): DocumentCategoryTreeNode[] {
  const result: DocumentCategoryTreeNode[] = [];
  for (const node of nodes) {
    result.push(node);
    if (node.children.length > 0) {
      result.push(...flattenCategoryTree(node.children));
    }
  }
  return result;
}

function findCategoryById(id: number): DocumentCategoryTreeNode | undefined {
  return flattenCategoryTree(categories.value).find((c) => c.id === id);
}

function collectCategorySelectOptions(
  nodes: DocumentCategoryTreeNode[],
  depth = 0,
  parentPath = "",
): CategorySelectOption[] {
  const options: CategorySelectOption[] = [];
  for (const node of nodes) {
    const path = parentPath ? `${parentPath}/${node.name}` : node.name;
    options.push({
      id: node.id,
      depth,
      label: node.name,
      path,
      node,
    });
    if (node.children.length > 0) {
      options.push(...collectCategorySelectOptions(node.children, depth + 1, path));
    }
  }
  return options;
}

function collectVisibleCategoryItems(
  nodes: DocumentCategoryTreeNode[],
  expandedIds: Set<number>,
  depth = 0,
  parentPath = "",
): CategoryTreeListItem[] {
  const items: CategoryTreeListItem[] = [];
  for (const node of nodes) {
    const path = parentPath ? `${parentPath}/${node.name}` : node.name;
    const hasChildren = node.children.length > 0;
    items.push({
      node,
      depth,
      path,
      hasChildren,
    });
    if (hasChildren && expandedIds.has(node.id)) {
      items.push(...collectVisibleCategoryItems(node.children, expandedIds, depth + 1, path));
    }
  }
  return items;
}

const categorySelectOptions = computed(() => collectCategorySelectOptions(categories.value));
const visibleCategoryItems = computed(() =>
  collectVisibleCategoryItems(categories.value, expandedCategoryIds.value),
);

const isForbidden = computed(() => Boolean(loadError.value) && isForbiddenError(loadError.value));
const selectedCategory = computed(() =>
  typeof selectedCategoryKey.value === "number"
    ? findCategoryById(selectedCategoryKey.value) ?? null
    : null,
);
const currentCategoryLabel = computed(() => {
  if (typeof selectedCategoryKey.value !== "number") {
    return "全部文档";
  }
  return getUploadCategoryPath(selectedCategoryKey.value) ?? "全部文档";
});
const selectedDocumentIds = computed(() => selectedDocuments.value.map((item) => item.id));
const hasDocumentSelection = computed(() => selectedDocuments.value.length > 0);
const existingCategoryPaths = computed(() => new Set(categorySelectOptions.value.map((item) => item.path)));
const selectedDocumentStatus = computed(() => {
  if (selectedDocuments.value.length === 0) {
    return null;
  }

  const [first] = selectedDocuments.value;
  return selectedDocuments.value.every((item) => item.status === first.status) ? first.status : null;
});
const canBatchSubmitForReview = computed(
  () => selectedDocumentStatus.value === "draft" && hasDocumentSelection.value,
);
const canBatchReject = computed(
  () => selectedDocumentStatus.value === "pending_review" && hasDocumentSelection.value,
);
const canBatchPublish = computed(
  () =>
    (selectedDocumentStatus.value === "pending_review" || selectedDocumentStatus.value === "archived") &&
    hasDocumentSelection.value,
);
const canBatchUnpublish = computed(
  () => selectedDocumentStatus.value === "published" && hasDocumentSelection.value,
);
const canRunOneClickSubmit = computed(
  () => documentQuery.status === "draft" && documentQuery.total > 0,
);
const canRunOneClickPublish = computed(
  () =>
    (documentQuery.status === "pending_review" || documentQuery.status === "archived") &&
    documentQuery.total > 0,
);
const pageTitle = computed(() => knowledgeBase.value?.name ?? "知识库详情");
const pageDescription = computed(() => knowledgeBase.value?.description?.trim() || "当前知识库用于统一管理分类、文档和索引状态。");
const summaryStats = computed(() => {
  if (!knowledgeBase.value) {
    return [];
  }

  return [
    { label: "文档总数", value: String(knowledgeBase.value.document_count) },
    {
      label: "索引中",
      value: String(knowledgeBase.value.queued_document_count + knowledgeBase.value.processing_document_count),
    },
  ];
});
const documentStatusTabs = computed<DocumentStatusTabItem[]>(() => {
  const sc = documentStatusCounts.value;
  const total = (sc.draft ?? 0) + (sc.pending_review ?? 0) + (sc.published ?? 0) + (sc.archived ?? 0);
  return [
    {
      label: "全部文档",
      value: "",
      count: total ?? null,
    },
    {
      label: "草稿",
      value: "draft",
      count: sc.draft ?? null,
    },
    {
      label: "待审核",
      value: "pending_review",
      count: sc.pending_review ?? null,
    },
    {
      label: "已发布",
      value: "published",
      count: sc.published ?? null,
    },
    {
      label: "已下线",
      value: "archived",
      count: sc.archived ?? null,
    },
  ];
});

function getPublishActionText(status: DocumentLifecycleStatus | null) {
  return status === "archived" ? "重新上线" : "通过并上线";
}

function getPublishBatchActionText(status: DocumentLifecycleStatus | null) {
  return status === "archived" ? "批量重新上线" : "批量通过并上线";
}

function getPublishConfirmText(status: DocumentLifecycleStatus | null) {
  return status === "archived" ? "重新上线" : "通过并上线";
}

function getOneClickPublishHint(status: DocumentLifecycleStatus | null) {
  return status === "archived"
    ? "确定将当前筛选下的已下线文档一次性重新上线吗？"
    : "确定将当前筛选下的待审核文档一次性通过并发布吗？";
}

function getKnowledgeBaseId() {
  const raw = Number(route.params.knowledgeBaseId);
  return Number.isInteger(raw) && raw > 0 ? raw : null;
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "暂无";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatFileSize(size: number) {
  if (!Number.isFinite(size) || size <= 0) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB"];
  let value = size;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${value.toFixed(value >= 100 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function getDocumentTypeLabel(documentType: string | null) {
  if (!documentType) {
    return "未知";
  }

  return documentType.toUpperCase();
}

function getIndexStatusMeta(status: DocumentSummary["index_status"] | DocumentSummary["graph_index_status"]) {
  const metaMap = {
    skipped: { label: "已跳过", type: "info" as const },
    queued: { label: "排队中", type: "warning" as const },
    processing: { label: "处理中", type: "primary" as const },
    finalizing: { label: "收尾中", type: "primary" as const },
    indexed: { label: "已索引", type: "success" as const },
    failed: { label: "失败", type: "danger" as const },
  };

  return metaMap[status];
}

function getParseStatusMeta(status: DocumentSummary["parse_status"]) {
  const metaMap = {
    queued: { label: "待解析", type: "warning" as const },
    processing: { label: "解析中", type: "primary" as const },
    parsed: { label: "已解析", type: "success" as const },
    failed: { label: "解析失败", type: "danger" as const },
  };

  return metaMap[status];
}

function getParseErrorText(status: DocumentSummary["parse_status"]) {
  if (status !== "failed") {
    return "";
  }

  return "解析失败，请检查原文件后重传。";
}

function getIndexErrorText(
  status: DocumentSummary["index_status"] | DocumentSummary["graph_index_status"],
) {
  if (status !== "failed") {
    return "";
  }

  return "索引失败，请稍后重试。";
}

function getLifecycleStatusMeta(status: DocumentLifecycleStatus) {
  const metaMap = {
    draft: { label: "草稿", type: "info" as const },
    pending_review: { label: "待审核", type: "warning" as const },
    published: { label: "已发布", type: "success" as const },
    archived: { label: "已归档", type: "info" as const },
  };

  return metaMap[status];
}

async function loadKnowledgeBaseSummary(knowledgeBaseId: number) {
  knowledgeBase.value = await getKnowledgeBase(knowledgeBaseId);
}

async function loadCategories(knowledgeBaseId: number) {
  categories.value = await listDocumentCategoriesTree(knowledgeBaseId);
  if (typeof selectedCategoryKey.value === "number") {
    const stillExists = flattenCategoryTree(categories.value).some((item) => item.id === selectedCategoryKey.value);
    if (!stillExists) {
      selectedCategoryKey.value = "all";
    }
  }
}

async function loadDocuments() {
  const knowledgeBaseId = getKnowledgeBaseId();
  if (!knowledgeBaseId) {
    loadError.value = new Error("知识库标识无效。");
    return;
  }

  documentsLoading.value = true;
  try {
    const response = await listDocuments({
      page: documentQuery.page,
      page_size: documentQuery.pageSize,
      keyword: documentQuery.keyword.trim() || undefined,
      team_id: teamScopeStore.selectedTeamId ?? undefined,
      knowledge_base_id: knowledgeBaseId,
      category_id:
        typeof selectedCategoryKey.value === "number" ? selectedCategoryKey.value : undefined,
      status: documentQuery.status || undefined,
    });
    documents.value = response.items;
    documentQuery.total = response.total;
    documentStatusCounts.value = response.status_counts ?? {};
    selectedDocuments.value = selectedDocuments.value.filter((item) =>
      response.items.some((doc) => doc.id === item.id),
    );
  } finally {
    documentsLoading.value = false;
  }
}

async function refreshKnowledgeBaseData() {
  if (!knowledgeBase.value) {
    return;
  }

  await Promise.all([
    loadKnowledgeBaseSummary(knowledgeBase.value.id),
    loadCategories(knowledgeBase.value.id),
    loadDocuments(),
  ]);
}

async function loadPage() {
  const knowledgeBaseId = getKnowledgeBaseId();
  if (!knowledgeBaseId) {
    loadError.value = new Error("知识库标识无效。");
    return;
  }

  pageLoading.value = true;
  loadError.value = null;
  try {
    await Promise.all([
      loadKnowledgeBaseSummary(knowledgeBaseId),
      loadCategories(knowledgeBaseId),
    ]);
    await loadDocuments();
  } catch (error) {
    loadError.value = error;
  } finally {
    pageLoading.value = false;
  }
}

function handleSelectCategory(key: CategoryFilterKey) {
  if (selectedCategoryKey.value === key) {
    return;
  }

  selectedCategoryKey.value = key;
  documentQuery.page = 1;
  void loadDocuments();
}

function handleSearch() {
  documentQuery.page = 1;
  selectedDocuments.value = [];
  void loadDocuments();
}

function resetSearch() {
  documentQuery.keyword = "";
  documentQuery.status = "";
  documentQuery.page = 1;
  selectedDocuments.value = [];
  void loadDocuments();
}

function handleSelectDocumentStatus(status: "" | DocumentLifecycleStatus) {
  if (documentQuery.status === status) {
    return;
  }

  documentQuery.status = status;
  documentQuery.page = 1;
  selectedDocuments.value = [];
  void loadDocuments();
}

async function promptCategoryName(options: {
  title: string;
  initialValue?: string;
}) {
  try {
    const { value } = await ElMessageBox.prompt("请输入分类名称", options.title, {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      inputValue: options.initialValue ?? "",
      inputPattern: /\S+/,
      inputErrorMessage: "分类名称不能为空",
    });
    return value.trim();
  } catch {
    return null;
  }
}

async function handleCreateCategory() {
  const knowledgeBaseId = getKnowledgeBaseId();
  if (!knowledgeBaseId || categoryActionLoading.value) {
    return;
  }

  const name = await promptCategoryName({ title: "新建分类" });
  if (!name) {
    return;
  }

  categoryActionLoading.value = true;
  try {
    await createDocumentCategory({
      knowledge_base_id: knowledgeBaseId,
      name,
    });
    ElMessage.success(`已创建分类"${name}"。`);
    await loadCategories(knowledgeBaseId);
  } catch (error) {
    const message = error instanceof Error ? error.message : "创建分类失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    categoryActionLoading.value = false;
  }
}

async function handleCreateSubcategory(parentCategory: DocumentCategoryTreeNode) {
  const knowledgeBaseId = getKnowledgeBaseId();
  if (!knowledgeBaseId || categoryActionLoading.value) {
    return;
  }

  const name = await promptCategoryName({ title: `在"${parentCategory.name}"下新建子分类` });
  if (!name) {
    return;
  }

  categoryActionLoading.value = true;
  try {
    await createDocumentCategory({
      knowledge_base_id: knowledgeBaseId,
      name,
      parent_id: parentCategory.id,
    });
    ElMessage.success(`已创建子分类"${name}"。`);
    expandedCategoryIds.value.add(parentCategory.id);
    await loadCategories(knowledgeBaseId);
  } catch (error) {
    const message = error instanceof Error ? error.message : "创建子分类失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    categoryActionLoading.value = false;
  }
}

async function handleRenameCategory(category: DocumentCategoryTreeNode) {
  if (categoryActionLoading.value) {
    return;
  }

  const name = await promptCategoryName({
    title: `重命名"${category.name}"`,
    initialValue: category.name,
  });
  if (!name || name === category.name) {
    return;
  }

  categoryActionLoading.value = true;
  try {
    await updateDocumentCategory(category.id, { name });
    ElMessage.success(`已将分类更新为"${name}"。`);
    await loadCategories(category.knowledge_base_id);
    await loadDocuments();
  } catch (error) {
    const message = error instanceof Error ? error.message : "更新分类失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    categoryActionLoading.value = false;
  }
}

async function handleDeleteCategory(category: DocumentCategoryTreeNode) {
  if (categoryActionLoading.value) {
    return;
  }

  const hasChildren = category.children && category.children.length > 0;
  const suffix = hasChildren ? "子分类也将被删除，已归属的文档会失去分类标记。" : "已归属到该分类的文档会失去分类标记。";

  try {
    await ElMessageBox.confirm(
      `确定删除分类"${category.name}"吗？${suffix}`,
      "删除分类",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  categoryActionLoading.value = true;
  try {
    await deleteDocumentCategory(category.id);
    ElMessage.success(`已删除分类"${category.name}"。`);
    if (selectedCategoryKey.value === category.id) {
      selectedCategoryKey.value = "all";
    }
    await loadCategories(category.knowledge_base_id);
    await loadDocuments();
  } catch (error) {
    const message = error instanceof Error ? error.message : "删除分类失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    categoryActionLoading.value = false;
  }
}

function handleUploadClick() {
  if (!knowledgeBase.value || uploadLoading.value) {
    return;
  }

  uploadTargetCategory.value = selectedCategory.value?.id ?? "uncategorized";
  uploadQueue.value = [];
  uploadDialogVisible.value = true;
}

function closeUploadDialog() {
  if (uploadLoading.value) {
    return;
  }

  uploadDialogVisible.value = false;
}

function handleUploadDialogClosed() {
  uploadQueue.value = [];
  uploadDragging.value = false;
  uploadTargetCategory.value = selectedCategory.value?.id ?? "uncategorized";
}

function triggerFileSelect() {
  if (uploadLoading.value) {
    return;
  }

  fileInputRef.value?.click();
}

function triggerFolderSelect() {
  if (uploadLoading.value) {
    return;
  }

  folderInputRef.value?.click();
}

function getUploadCategoryPath(categoryId: number): string | null {
  return categorySelectOptions.value.find((item) => item.id === categoryId)?.path ?? null;
}

function getCategoryOptionLabel(option: CategorySelectOption) {
  return option.depth > 0 ? `${"|  ".repeat(option.depth)}${option.label}` : option.label;
}

function getUploadTargetRootPath() {
  if (uploadTargetCategory.value === "uncategorized") {
    return null;
  }

  return getUploadCategoryPath(uploadTargetCategory.value as number);
}

function buildMountedCategoryPath(sourcePath: string): string | null {
  const segments = sourcePath.replace(/\\/g, "/").split("/").filter(Boolean);
  const folderSegments = segments.length > 1 ? segments.slice(0, -1) : [];
  const rootPath = getUploadTargetRootPath();
  const mountedSegments = [
    ...(rootPath ? rootPath.split("/").filter(Boolean) : []),
    ...folderSegments,
  ];
  if (mountedSegments.length === 0) {
    return null;
  }
  return mountedSegments.join("/");
}

function buildUploadQueueItem(file: UploadInputFile): UploadQueueItem {
  const path = (file.customPath || file.webkitRelativePath || file.name).replace(/\\/g, "/").trim();
  const normalizedPath = path || file.name;
  const mountedCategoryPath = buildMountedCategoryPath(normalizedPath);
  return {
    raw: file,
    name: file.name,
    path: normalizedPath,
    category: mountedCategoryPath ?? "未分类",
    isNewCategory: mountedCategoryPath ? !existingCategoryPaths.value.has(mountedCategoryPath) : false,
    size: file.size,
  };
}

function syncUploadQueueWithTargetCategory() {
  uploadQueue.value = uploadQueue.value.map((item) => {
    const mountedCategoryPath = buildMountedCategoryPath(item.path);
    return {
      ...item,
      category: mountedCategoryPath ?? "未分类",
      isNewCategory: mountedCategoryPath ? !existingCategoryPaths.value.has(mountedCategoryPath) : false,
    };
  });
}

function processUploadFiles(rawFiles: UploadInputFile[]) {
  const seenPaths = new Set(uploadQueue.value.map((item) => item.path));

  for (const file of rawFiles) {
    const queueItem = buildUploadQueueItem(file);
    if (seenPaths.has(queueItem.path)) {
      continue;
    }
    seenPaths.add(queueItem.path);
    uploadQueue.value.push(queueItem);
  }

  syncUploadQueueWithTargetCategory();
}

async function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  const files = Array.from(target.files ?? []).map((file) => {
    const uploadFile = file as UploadInputFile;
    uploadFile.customPath = file.name;
    return uploadFile;
  });
  target.value = "";

  if (files.length === 0) {
    return;
  }

  processUploadFiles(files);
}

async function handleFolderChange(event: Event) {
  const target = event.target as HTMLInputElement;
  const files = Array.from(target.files ?? []).map((file) => {
    const uploadFile = file as UploadInputFile;
    uploadFile.customPath = uploadFile.webkitRelativePath || file.name;
    return uploadFile;
  });
  target.value = "";

  if (files.length === 0) {
    return;
  }

  processUploadFiles(files);
}

async function traverseDroppedEntry(
  entry: FileSystemEntryLike,
  currentPath: string,
  files: UploadInputFile[],
) {
  if (entry.isFile && entry.file) {
    const file = await new Promise<File>((resolve) => entry.file!(resolve));
    const uploadFile = file as UploadInputFile;
    uploadFile.customPath = `${currentPath}${file.name}`;
    files.push(uploadFile);
    return;
  }

  if (!entry.isDirectory || !entry.createReader) {
    return;
  }

  const reader = entry.createReader();
  const directoryPath = `${currentPath}${entry.name}/`;
  while (true) {
    const entries = await new Promise<FileSystemEntryLike[]>((resolve) => reader.readEntries(resolve));
    if (entries.length === 0) {
      break;
    }
    for (const child of entries) {
      await traverseDroppedEntry(child, directoryPath, files);
    }
  }
}

async function handleUploadDrop(event: DragEvent) {
  uploadDragging.value = false;
  const items = Array.from(event.dataTransfer?.items ?? []);
  const files: UploadInputFile[] = [];

  for (const item of items) {
    if (item.kind !== "file") {
      continue;
    }

    const entry = (item as DataTransferItem & {
      webkitGetAsEntry?: () => FileSystemEntryLike | null;
    }).webkitGetAsEntry?.();

    if (entry) {
      await traverseDroppedEntry(entry, "", files);
      continue;
    }

    const file = item.getAsFile();
    if (!file) {
      continue;
    }
    const uploadFile = file as UploadInputFile;
    uploadFile.customPath = file.name;
    files.push(uploadFile);
  }

  if (files.length === 0) {
    return;
  }

  processUploadFiles(files);
}

function removeUploadFile(path: string) {
  uploadQueue.value = uploadQueue.value.filter((item) => item.path !== path);
}

function clearUploadQueue() {
  uploadQueue.value = [];
}

function buildUploadSourcePath(item: UploadQueueItem) {
  return item.path;
}

async function submitUploadQueue() {
  if (!knowledgeBase.value || uploadQueue.value.length === 0 || uploadLoading.value) {
    return;
  }

  const knowledgeBaseId = knowledgeBase.value.id;
  uploadLoading.value = true;
  try {
    const createdDocuments = await uploadDocumentsBatch({
      files: uploadQueue.value.map((item) => item.raw),
      knowledgeBaseId,
      categoryId: uploadTargetCategory.value === "uncategorized" ? null : uploadTargetCategory.value,
      sourcePaths: uploadQueue.value.map((item) => buildUploadSourcePath(item)),
    });
    ElMessage.success(`已提交 ${createdDocuments.length} 个文档的上传与解析任务。`);
    documentQuery.page = 1;
    uploadDialogVisible.value = false;
    await Promise.all([
      loadKnowledgeBaseSummary(knowledgeBaseId),
      loadCategories(knowledgeBaseId),
      loadDocuments(),
    ]);
  } catch (error) {
    const message = error instanceof Error ? error.message : "上传文档失败，请稍后重试。";
    try {
      await Promise.all([
        loadKnowledgeBaseSummary(knowledgeBaseId),
        loadCategories(knowledgeBaseId),
        loadDocuments(),
      ]);
    } catch {
      // 刷新失败时保留原始上传错误提示，避免二次错误覆盖。
    }
    ElMessage.error(message);
  } finally {
    uploadLoading.value = false;
  }
}

function handleDocumentSelectionChange(items: unknown[]) {
  selectedDocuments.value = items as DocumentSummary[];
}

async function runBatchDocumentAction(
  documentIds: number[],
  title: string,
  message: string,
  action: (ids: number[]) => Promise<{
    succeeded_count: number;
    failed_count: number;
    failures: Array<{ document_id: number; detail: string }>;
  }>,
  successPrefix: string,
) {
  if (documentActionLoading.value || documentIds.length === 0) {
    return;
  }

  try {
    await ElMessageBox.confirm(message, title, {
      type: "warning",
      confirmButtonText: "确定",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }

  documentActionLoading.value = true;
  try {
    const result = await action(documentIds);
    const succeeded = result.succeeded_count;
    const failed = result.failed_count;
    selectedDocuments.value = [];

    if (succeeded > 0) {
      ElMessage.success(`已${successPrefix}${succeeded}个文档。`);
    }
    if (failed > 0) {
      ElMessage.warning(`${failed} 个文档处理失败，请检查文档状态后重试。`);
    }

    await refreshKnowledgeBaseData();
  } catch (error) {
    const fallback = `${title}失败，请稍后重试。`;
    const messageText = error instanceof Error ? error.message : fallback;
    ElMessage.error(messageText);
  } finally {
    documentActionLoading.value = false;
  }
}

async function runOneClickDocumentAction(
  title: string,
  message: string,
  action: () => Promise<{
    succeeded_count: number;
    failed_count: number;
    failures: Array<{ document_id: number; detail: string }>;
  }>,
  successPrefix: string,
) {
  if (documentActionLoading.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(message, title, {
      type: "warning",
      confirmButtonText: "确定",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }

  documentActionLoading.value = true;
  try {
    const result = await action();
    const succeeded = result.succeeded_count;
    const failed = result.failed_count;

    if (succeeded > 0) {
      ElMessage.success(`已${successPrefix}${succeeded}个文档。`);
    } else {
      ElMessage.info("当前筛选下没有可处理的文档。");
    }
    if (failed > 0) {
      ElMessage.warning(`${failed} 个文档处理失败，请检查文档状态后重试。`);
    }

    await refreshKnowledgeBaseData();
  } catch (error) {
    const fallback = `${title}失败，请稍后重试。`;
    const messageText = error instanceof Error ? error.message : fallback;
    ElMessage.error(messageText);
  } finally {
    documentActionLoading.value = false;
  }
}

async function handleDeleteOneDocument(document: DocumentSummary) {
  if (documentActionLoading.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定删除文档"${document.title}"吗？删除后不可恢复。`,
      "删除文档",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  documentActionLoading.value = true;
  try {
    await deleteDocument(document.id);
    ElMessage.success(`已删除文档"${document.title}"。`);
    if (knowledgeBase.value) {
      await Promise.all([
        loadKnowledgeBaseSummary(knowledgeBase.value.id),
        loadCategories(knowledgeBase.value.id),
        loadDocuments(),
      ]);
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "删除文档失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    documentActionLoading.value = false;
  }
}

async function handleBatchDeleteDocuments() {
  if (!hasDocumentSelection.value || documentActionLoading.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定删除已选中的 ${selectedDocuments.value.length} 个文档吗？删除后不可恢复。`,
      "批量删除文档",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  documentActionLoading.value = true;
  try {
    await deleteDocumentsBatch(selectedDocumentIds.value);
    selectedDocuments.value = [];
    ElMessage.success("已删除所选文档。");
    if (knowledgeBase.value) {
      await Promise.all([
        loadKnowledgeBaseSummary(knowledgeBase.value.id),
        loadCategories(knowledgeBase.value.id),
        loadDocuments(),
      ]);
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "批量删除失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    documentActionLoading.value = false;
  }
}

async function handleIndexDocument(document: DocumentSummary) {
  if (documentActionLoading.value) {
    return;
  }

  documentActionLoading.value = true;
  try {
    await indexDocument(document.id);
    ElMessage.success(`已提交"${document.title}"的重建索引任务。`);
    await loadDocuments();
  } catch (error) {
    const message = error instanceof Error ? error.message : "提交索引任务失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    documentActionLoading.value = false;
  }
}

async function handleSubmitDocumentForReview(document: DocumentSummary) {
  await runBatchDocumentAction(
    [document.id],
    "提交审核",
    `确定将文档"${document.title}"提交审核吗？`,
    submitDocumentsForReviewBatch,
    "提交审核",
  );
}

async function handleRejectDocument(document: DocumentSummary) {
  await runBatchDocumentAction(
    [document.id],
    "驳回",
    `确定驳回文档"${document.title}"吗？驳回后会回到草稿状态。`,
    rejectDocumentsBatch,
    "驳回",
  );
}

async function handlePublishDocument(document: DocumentSummary) {
  const actionText = getPublishActionText(document.status);
  await runBatchDocumentAction(
    [document.id],
    actionText,
    `确定${getPublishConfirmText(document.status)}文档"${document.title}"吗？`,
    publishDocumentsBatch,
    actionText,
  );
}

async function handleUnpublishDocument(document: DocumentSummary) {
  await runBatchDocumentAction(
    [document.id],
    "下线",
    `确定下线文档"${document.title}"吗？`,
    unpublishDocumentsBatch,
    "下线",
  );
}

async function handleBatchSubmitForReview() {
  await runBatchDocumentAction(
    selectedDocumentIds.value,
    "批量提交审核",
    `确定将选中的 ${selectedDocuments.value.length} 个文档提交审核吗？`,
    submitDocumentsForReviewBatch,
    "提交审核",
  );
}

async function handleBatchReject() {
  await runBatchDocumentAction(
    selectedDocumentIds.value,
    "批量驳回",
    `确定驳回选中的 ${selectedDocuments.value.length} 个文档吗？`,
    rejectDocumentsBatch,
    "驳回",
  );
}

async function handleBatchPublish() {
  const actionText = getPublishBatchActionText(selectedDocumentStatus.value);
  await runBatchDocumentAction(
    selectedDocumentIds.value,
    actionText,
    `确定${getPublishConfirmText(selectedDocumentStatus.value)}选中的 ${selectedDocuments.value.length} 个文档吗？`,
    publishDocumentsBatch,
    getPublishActionText(selectedDocumentStatus.value),
  );
}

async function handleBatchUnpublish() {
  await runBatchDocumentAction(
    selectedDocumentIds.value,
    "批量下线",
    `确定下线选中的 ${selectedDocuments.value.length} 个文档吗？`,
    unpublishDocumentsBatch,
    "下线",
  );
}

async function handleOneClickSubmitForReview() {
  if (!canRunOneClickSubmit.value) {
    return;
  }

  await runOneClickDocumentAction(
    "一键提交审核",
    `确定将当前筛选下的草稿文档一次性提交审核吗？`,
    async () =>
      submitDocumentsForReviewByFilter({
        keyword: documentQuery.keyword.trim() || undefined,
        team_id: teamScopeStore.selectedTeamId ?? undefined,
        knowledge_base_id: getKnowledgeBaseId() ?? undefined,
        category_id: typeof selectedCategoryKey.value === "number" ? selectedCategoryKey.value : undefined,
      }),
    "提交审核",
  );
}

async function handleOneClickPublish() {
  if (!canRunOneClickPublish.value) {
    return;
  }

  const actionText = getPublishActionText(documentQuery.status || null);
  await runOneClickDocumentAction(
    `一键${actionText}`,
    getOneClickPublishHint(documentQuery.status || null),
    async () =>
      publishDocumentsByFilter({
        keyword: documentQuery.keyword.trim() || undefined,
        team_id: teamScopeStore.selectedTeamId ?? undefined,
        knowledge_base_id: getKnowledgeBaseId() ?? undefined,
        category_id: typeof selectedCategoryKey.value === "number" ? selectedCategoryKey.value : undefined,
      }),
    actionText,
  );
}

async function handleReindexKnowledgeBase() {
  if (!knowledgeBase.value || documentActionLoading.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定重建知识库"${knowledgeBase.value.name}"的索引吗？该操作会重新提交全部文档的索引任务，处理中可能短暂影响检索结果。`,
      "重建知识库索引",
      {
        type: "warning",
        confirmButtonText: "继续重建",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  documentActionLoading.value = true;
  try {
    await reindexKnowledgeBaseDocuments(knowledgeBase.value.id);
    ElMessage.success(`已提交"${knowledgeBase.value.name}"的重建索引任务。`);
    await loadDocuments();
  } catch (error) {
    const message = error instanceof Error ? error.message : "提交重建索引任务失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    documentActionLoading.value = false;
  }
}

function handleOpenDocumentDetail(document: DocumentSummary) {
  if (!knowledgeBase.value) {
    return;
  }

  const routeName = typeof route.name === "string" ? route.name : "";
  const isEvaluationKnowledgeBaseRoute =
    routeName === "evaluation-knowledge-base-detail" ||
    routeName === "evaluation-knowledge-base-document-detail";

  if (isEvaluationKnowledgeBaseRoute) {
    void router.push(`/evaluations/knowledge-bases/${knowledgeBase.value.id}/documents/${document.id}`);
    return;
  }

  void router.push(`/knowledge-bases/${knowledgeBase.value.id}/documents/${document.id}`);
}

function handlePageChange(page: number) {
  documentQuery.page = page;
  void loadDocuments();
}

onMounted(() => {
  void loadPage();
});

watch(
  () => knowledgeBase.value?.name,
  (name) => {
    adminBreadcrumbStore.setDynamicTitle("knowledge-base-detail", name);
    adminBreadcrumbStore.setDynamicTitle("evaluation-knowledge-base-detail", name);
  },
  { immediate: true },
);

watch(
  () => teamScopeStore.selectedTeamId,
  () => {
    selectedDocuments.value = [];
    documentQuery.page = 1;
    selectedCategoryKey.value = "all";
    void loadPage();
  },
);

watch(
  () => route.params.knowledgeBaseId,
  () => {
    selectedDocuments.value = [];
    documentQuery.page = 1;
    selectedCategoryKey.value = "all";
    void loadPage();
  },
);

watch(
  [uploadTargetCategory, categories],
  () => {
    syncUploadQueueWithTargetCategory();
  },
  { deep: true },
);
</script>

<template>
  <section class="kb-detail-page">
    <AppLoading
      v-if="pageLoading"
      title="知识库详情加载中"
      description="正在准备分类与文档列表，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="loadError && !isForbidden"
      title="知识库详情加载失败"
      description="暂时无法获取知识库详情，请稍后重试。"
      :error="loadError"
      @retry="loadPage"
    />

    <AppError
      v-else-if="isForbidden"
      title="无权查看知识库详情"
      description="当前账号没有访问该知识库详情页的权限。"
      :error="loadError"
      :show-retry="false"
    />

    <template v-else-if="knowledgeBase">
      <section class="kb-detail-page__layout">
        <aside class="kb-sidebar">
          <div class="kb-sidebar__header">
            <div>
              <h2 class="kb-sidebar__title">文档分类</h2>
            </div>
            <el-button
              type="primary"
              link
              :disabled="categoryActionLoading"
              @click="handleCreateCategory"
            >
              <el-icon><CirclePlus /></el-icon>
            </el-button>
          </div>

          <div class="kb-sidebar__list">
            <div
              :class="[
                'kb-sidebar__item',
                selectedCategoryKey === 'all' ? 'kb-sidebar__item--active' : '',
              ]"
              role="button"
              tabindex="0"
              @click="handleSelectCategory('all')"
              @keyup.enter="handleSelectCategory('all')"
            >
              <span class="kb-sidebar__item-main">
                <el-icon><Folder /></el-icon>
                <span class="kb-sidebar__item-label">全部文档</span>
              </span>
              <span v-if="knowledgeBase?.document_count != null" class="kb-sidebar__item-count">{{ knowledgeBase.document_count }}</span>
            </div>

            <template v-for="item in visibleCategoryItems" :key="item.node.id">
              <div
                :class="[
                  'kb-sidebar__item',
                  selectedCategoryKey === item.node.id ? 'kb-sidebar__item--active' : '',
                ]"
                :style="{ paddingLeft: `${14 + item.depth * 26}px` }"
                role="button"
                tabindex="0"
                @click="handleSelectCategory(item.node.id)"
                @keyup.enter="handleSelectCategory(item.node.id)"
              >
                <span class="kb-sidebar__item-main">
                  <button
                    v-if="item.hasChildren"
                    type="button"
                    class="kb-sidebar__toggle"
                    @click.stop="expandedCategoryIds.has(item.node.id) ? expandedCategoryIds.delete(item.node.id) : expandedCategoryIds.add(item.node.id)"
                  >
                    <el-icon :class="{ 'is-rotated': expandedCategoryIds.has(item.node.id) }"><ArrowRight /></el-icon>
                  </button>
                  <el-icon v-else><Folder /></el-icon>
                  <span class="kb-sidebar__item-label">{{ item.node.name }}</span>
                </span>

                <span class="kb-sidebar__item-side">
                  <span class="kb-sidebar__item-count">{{ item.node.document_count }}</span>
                  <el-dropdown
                    trigger="click"
                    placement="bottom-end"
                    @command="(command: string) => {
                      if (command === 'rename') {
                        void handleRenameCategory(item.node);
                        return;
                      }
                      if (command === 'create-sub') {
                        void handleCreateSubcategory(item.node);
                        return;
                      }
                      if (command === 'delete') {
                        void handleDeleteCategory(item.node);
                      }
                    }"
                  >
                    <button type="button" class="kb-sidebar__item-more" @click.stop>
                      <el-icon><MoreFilled /></el-icon>
                    </button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="rename">
                          <el-icon><EditPen /></el-icon>
                          <span>重命名</span>
                        </el-dropdown-item>
                        <el-dropdown-item command="create-sub">
                          <el-icon><CirclePlus /></el-icon>
                          <span>新建子分类</span>
                        </el-dropdown-item>
                        <el-dropdown-item command="delete">
                          <el-icon><Delete /></el-icon>
                          <span>删除</span>
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </span>
              </div>
            </template>
          </div>
        </aside>

        <div class="kb-documents">
          <AdminListPanel>
            <AdminTableToolbar>
              <template #left>
                <span class="kb-documents__current-category">{{ currentCategoryLabel }}</span>
                <el-input
                  v-model="documentQuery.keyword"
                  clearable
                  placeholder="搜索文档标题..."
                  class="kb-documents__search"
                  @clear="handleSearch"
                  @keyup.enter="handleSearch"
                >
                  <template #prefix>
                    <el-icon><Search /></el-icon>
                  </template>
                </el-input>

                <el-button @click="resetSearch">重置</el-button>
              </template>

              <template #right>
                <el-select
                  v-model="documentQuery.status"
                  class="kb-documents__status-filter"
                  placeholder="业务状态"
                  @change="(value: '' | DocumentLifecycleStatus) => handleSelectDocumentStatus(value)"
                >
                  <template #prefix>
                    <span class="kb-documents__filter-prefix">业务状态</span>
                  </template>
                  <el-option
                    v-for="tab in documentStatusTabs"
                    :key="tab.value || 'all'"
                    :label="`${tab.label} ${tab.count ?? 0}`"
                    :value="tab.value"
                  />
                </el-select>
                <AdminBulkActions :selected-count="selectedDocuments.length">
                  <el-button
                    v-if="canBatchSubmitForReview"
                    link
                    type="warning"
                    :disabled="documentActionLoading"
                    @click="handleBatchSubmitForReview"
                  >
                    提交审核
                  </el-button>
                  <el-button
                    v-if="canBatchReject"
                    link
                    type="danger"
                    :disabled="documentActionLoading"
                    @click="handleBatchReject"
                  >
                    驳回
                  </el-button>
                  <el-button
                    v-if="canBatchPublish"
                    link
                    type="primary"
                    :disabled="documentActionLoading"
                    @click="handleBatchPublish"
                  >
                    {{ getPublishBatchActionText(selectedDocumentStatus) }}
                  </el-button>
                  <el-button
                    v-if="canBatchUnpublish"
                    link
                    type="warning"
                    :disabled="documentActionLoading"
                    @click="handleBatchUnpublish"
                  >
                    下线
                  </el-button>
                  <el-button
                    link
                    type="danger"
                    :disabled="documentActionLoading"
                    @click="handleBatchDeleteDocuments"
                  >
                    删除
                  </el-button>
                </AdminBulkActions>
                <el-button
                  v-if="canRunOneClickSubmit"
                  type="warning"
                  :disabled="documentActionLoading"
                  @click="handleOneClickSubmitForReview"
                >
                  一键提交审核
                </el-button>
                <el-button
                  v-if="canRunOneClickPublish"
                  type="primary"
                  :disabled="documentActionLoading"
                  @click="handleOneClickPublish"
                >
                  {{ `一键${getPublishActionText(documentQuery.status || null)}` }}
                </el-button>
                <el-button @click="detailDrawerVisible = true">
                  <el-icon class="mr-2"><InfoFilled /></el-icon>
                  详情
                </el-button>
                <el-button
                  :loading="documentActionLoading"
                  :disabled="!knowledgeBase"
                  @click="handleReindexKnowledgeBase"
                >
                  <el-icon class="mr-2"><RefreshRight /></el-icon>
                  重建索引
                </el-button>
                <el-button
                  type="primary"
                  :loading="uploadLoading"
                  @click="handleUploadClick"
                >
                  <el-icon class="mr-2"><UploadFilled /></el-icon>
                  上传文档
                </el-button>
              </template>
            </AdminTableToolbar>

            <section class="kb-documents__content">
            <AppEmpty
              v-if="!documentsLoading && documents.length === 0"
              title="当前没有可展示的文档"
              description="可以调整筛选条件，或直接上传新文档到当前知识库。"
            >
              <el-button link type="primary" @click="handleUploadClick">上传文档</el-button>
            </AppEmpty>

            <AdminDataTable
              v-else
              :data="documents"
              :loading="documentsLoading"
              table-class="kb-documents__table"
              @selection-change="handleDocumentSelectionChange"
            >
              <el-table-column type="selection" width="48" />
              <el-table-column label="文档标题" min-width="280" show-overflow-tooltip>
                <template #default="{ row }">
                  <div class="kb-documents__name-cell">
                    <el-icon><Document /></el-icon>
                    <div class="kb-documents__name-copy">
                      <strong>{{ row.title }}</strong>
                      <span>{{ row.category_name || "未分配分类" }}</span>
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="类型" width="100">
                <template #default="{ row }">
                  <span>{{ getDocumentTypeLabel(row.document_type) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="大小" width="110">
                <template #default="{ row }">
                  <span>{{ formatFileSize(row.size) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="解析状态" width="140">
                <template #default="{ row }">
                  <div class="kb-documents__index-cell">
                    <StatusTag
                      :label="getParseStatusMeta(row.parse_status).label"
                      :type="getParseStatusMeta(row.parse_status).type"
                    />
                    <span
                      v-if="row.parse_status === 'failed'"
                      class="kb-documents__index-error"
                      :title="getParseErrorText(row.parse_status)"
                    >
                      {{ getParseErrorText(row.parse_status) }}
                    </span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="文本索引" width="140">
                <template #default="{ row }">
                  <div class="kb-documents__index-cell">
                    <StatusTag
                      :label="getIndexStatusMeta(row.index_status).label"
                      :type="getIndexStatusMeta(row.index_status).type"
                    />
                    <span
                      v-if="row.index_status === 'failed'"
                      class="kb-documents__index-error"
                      :title="getIndexErrorText(row.index_status)"
                    >
                      {{ getIndexErrorText(row.index_status) }}
                    </span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="图谱索引" width="140">
                <template #default="{ row }">
                  <div class="kb-documents__index-cell">
                    <StatusTag
                      :label="getIndexStatusMeta(row.graph_index_status).label"
                      :type="getIndexStatusMeta(row.graph_index_status).type"
                    />
                    <span
                      v-if="row.graph_index_status === 'failed'"
                      class="kb-documents__index-error"
                      :title="getIndexErrorText(row.graph_index_status)"
                    >
                      {{ getIndexErrorText(row.graph_index_status) }}
                    </span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="发布状态" width="120">
                <template #default="{ row }">
                  <StatusTag
                    :label="getLifecycleStatusMeta(row.status).label"
                    :type="getLifecycleStatusMeta(row.status).type"
                  />
                </template>
              </el-table-column>
              <el-table-column label="最后更新" width="180">
                <template #default="{ row }">
                  <span>{{ formatDateTime(row.updated_at) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="360" fixed="right" align="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="handleOpenDocumentDetail(row)">
                    <el-icon><View /></el-icon>
                    <span>查看</span>
                  </el-button>
                  <el-button link type="primary" @click="handleIndexDocument(row)">
                    <el-icon><RefreshRight /></el-icon>
                    <span>索引</span>
                  </el-button>
                  <el-button v-if="row.status === 'draft'" link type="warning" @click="handleSubmitDocumentForReview(row)">
                    <span>提交审核</span>
                  </el-button>
                  <el-button v-else-if="row.status === 'pending_review' || row.status === 'archived'" link type="success" @click="handlePublishDocument(row)">
                    <span>{{ getPublishActionText(row.status) }}</span>
                  </el-button>
                  <el-button v-else-if="row.status === 'published'" link type="warning" @click="handleUnpublishDocument(row)">
                    <span>下线</span>
                  </el-button>
                  <el-button v-if="row.status === 'pending_review'" link type="danger" @click="handleRejectDocument(row)">
                    <span>驳回</span>
                  </el-button>
                  <el-button link type="danger" @click="handleDeleteOneDocument(row)">
                    <el-icon><Delete /></el-icon>
                    <span>删除</span>
                  </el-button>
                </template>
              </el-table-column>
            </AdminDataTable>
            </section>

            <footer class="kb-documents__footer">
            <AdminPagination
              :total="documentQuery.total"
              :page-size="documentQuery.pageSize"
              :current-page="documentQuery.page"
              layout="total, prev, pager, next"
              @page-change="handlePageChange"
              @page-size-change="() => undefined"
            />
            </footer>
          </AdminListPanel>
        </div>
      </section>

      <AdminDialog
        v-model="uploadDialogVisible"
        width="960px"
        title="文档上传"
        class="kb-upload-dialog"
        :loading="uploadLoading"
        :close-on-click-modal="!uploadLoading"
        @closed="handleUploadDialogClosed"
      >
        <template #header>
          <div class="kb-upload-dialog__header">
            <div>
              <h3 class="kb-upload-dialog__title">文档上传</h3>
              <p class="kb-upload-dialog__subtitle">
                支持拖拽、选择文件或文件夹，并按目录结构自动映射分类。当前支持
                .txt、.md、.jsonl、.pdf、.docx、.doc 文件。
              </p>
            </div>

            <div class="kb-upload-dialog__target">
              <span class="kb-upload-dialog__target-label">上传至</span>
              <el-select v-model="uploadTargetCategory" class="kb-upload-dialog__target-select">
                <el-option :value="'uncategorized'" label="未分类（默认）" />
                <el-option
                  v-for="option in categorySelectOptions"
                  :key="option.id"
                  :value="option.id"
                  :label="getCategoryOptionLabel(option)"
                />
              </el-select>
            </div>
          </div>
        </template>

        <div class="kb-upload-dialog__body">
          <div
            class="kb-upload-dropzone"
            :class="{ 'is-dragging': uploadDragging }"
            @dragover.prevent="uploadDragging = true"
            @dragleave.prevent="uploadDragging = false"
            @drop.prevent="handleUploadDrop"
          >
            <div class="kb-upload-dropzone__icon">
              <el-icon :size="28"><UploadFilled /></el-icon>
            </div>
            <h4 class="kb-upload-dropzone__title">将文件或文件夹拖拽至此</h4>
            <p class="kb-upload-dropzone__hint">或者使用下方按钮手动选择</p>
            <div class="kb-upload-dropzone__actions">
              <el-button @click="triggerFileSelect">
                <el-icon class="mr-2"><Document /></el-icon>
                选择文件
              </el-button>
              <el-button type="primary" @click="triggerFolderSelect">
                <el-icon class="mr-2"><Folder /></el-icon>
                选择文件夹
              </el-button>
            </div>
            <input
              ref="fileInputRef"
              class="kb-documents__hidden-input"
              type="file"
              multiple
              @change="handleFileChange"
            >
            <input
              ref="folderInputRef"
              class="kb-documents__hidden-input"
              type="file"
              multiple
              webkitdirectory
              @change="handleFolderChange"
            >
          </div>

          <div v-if="uploadQueue.length > 0" class="kb-upload-queue">
            <div class="kb-upload-queue__header">
              <h4 class="kb-upload-queue__title">待上传列表（{{ uploadQueue.length }}）</h4>
              <el-button link type="danger" @click="clearUploadQueue">清空全部</el-button>
            </div>

            <div class="kb-upload-queue__table">
              <div class="kb-upload-queue__row kb-upload-queue__row--head">
                <span>文件名</span>
                <span>归属分类</span>
                <span>原始路径</span>
                <span class="is-right">大小</span>
                <span class="is-right">操作</span>
              </div>

              <div
                v-for="item in uploadQueue"
                :key="item.path"
                class="kb-upload-queue__row"
              >
                <span class="kb-upload-queue__file">
                  <el-icon><Document /></el-icon>
                  <span class="kb-upload-queue__file-name">{{ item.name }}</span>
                </span>
                <span>
                  <span
                    class="kb-upload-queue__category"
                    :class="{
                      'is-plain': item.category === '未分类',
                      'is-new': item.isNewCategory,
                    }"
                  >
                    {{ item.category }}
                    <span v-if="item.isNewCategory">（将自动创建）</span>
                  </span>
                </span>
                <span class="kb-upload-queue__path" :title="item.path">{{ item.path }}</span>
                <span class="is-right">{{ formatFileSize(item.size) }}</span>
                <span class="is-right">
                  <el-button link type="danger" @click="removeUploadFile(item.path)">移除</el-button>
                </span>
              </div>
            </div>
          </div>
        </div>

        <template #footer>
          <el-button :disabled="uploadLoading" @click="closeUploadDialog">取消</el-button>
          <el-button
            type="primary"
            :loading="uploadLoading"
            :disabled="uploadQueue.length === 0"
            @click="submitUploadQueue"
          >
            确认上传
          </el-button>
        </template>
      </AdminDialog>

      <el-drawer
        v-model="detailDrawerVisible"
        title="知识库详情"
        size="420px"
        append-to-body
      >
        <div class="kb-detail-drawer">
          <div class="kb-detail-drawer__title-block">
            <h3>{{ pageTitle }}</h3>
            <p>{{ pageDescription }}</p>
          </div>

          <div class="kb-detail-drawer__meta">
            <div>
              <span>所属团队</span>
              <strong>{{ teamScopeStore.selectedTeam?.name ?? "全部团队可见" }}</strong>
            </div>
            <div>
              <span>最近更新</span>
              <strong>{{ formatDateTime(knowledgeBase.last_document_updated_at ?? knowledgeBase.updated_at) }}</strong>
            </div>
            <div>
              <span>创建时间</span>
              <strong>{{ formatDateTime(knowledgeBase.created_at) }}</strong>
            </div>
          </div>

          <div class="kb-detail-drawer__stats">
            <div
              v-for="item in summaryStats"
              :key="item.label"
              class="kb-detail-drawer__stat"
            >
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </div>
      </el-drawer>
    </template>

  </section>
</template>

<style scoped>
.kb-detail-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.kb-detail-page__layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 20px;
}

.kb-sidebar {
  border: 1px solid #dbe2ea;
  border-radius: 22px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.kb-sidebar {
  display: flex;
  flex-direction: column;
  min-height: 680px;
}

.kb-sidebar__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px;
}

.kb-sidebar__title,
.kb-documents__title {
  margin: 0;
  color: #0f172a;
  font-size: 17px;
  font-weight: 700;
}

.kb-sidebar__hint,
.kb-documents__hint {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.kb-sidebar__list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  padding: 0 12px 14px;
}

.kb-sidebar__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid transparent;
  border-radius: 14px;
  background: transparent;
  color: #334155;
  cursor: pointer;
  padding: 12px 14px;
  text-align: left;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease;
}

.kb-sidebar__item:hover {
  background: #f8fafc;
}

.kb-sidebar__item--active {
  border-color: var(--admin-primary-border);
  background: var(--admin-primary-soft);
  color: var(--admin-primary-hover);
}

.kb-sidebar__item--child {
  padding-left: 40px;
}

.kb-sidebar__toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  padding: 2px;
  transition: transform 0.2s ease;
}

.kb-sidebar__toggle:hover {
  color: var(--admin-primary);
}

.kb-sidebar__toggle .is-rotated {
  transform: rotate(90deg);
}

.kb-sidebar__item-main,
.kb-sidebar__item-side {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.kb-sidebar__item-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 600;
}

.kb-sidebar__item-count {
  color: #94a3b8;
  font-size: 12px;
  font-weight: 600;
}

.kb-sidebar__item-more {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  padding: 4px;
}

.kb-sidebar__item-more:hover {
  background: rgba(255, 255, 255, 0.9);
  color: var(--admin-primary);
}

.kb-documents {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.kb-documents__current-category {
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
  white-space: nowrap;
}

.kb-documents__search {
  width: 280px;
}

.kb-documents__status-filter {
  width: 190px;
}

.kb-documents__filter-prefix {
  color: #64748b;
  font-size: 12px;
  white-space: nowrap;
}

.kb-documents__status {
  width: 150px;
}

.kb-documents__content {
  flex: 1;
  padding: 0;
}

.kb-documents__table {
  width: 100%;
}

.kb-documents__name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.kb-documents__name-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.kb-documents__name-copy strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-documents__name-copy span {
  color: #64748b;
  font-size: 12px;
}

.kb-documents__index-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.kb-documents__index-error {
  overflow: hidden;
  color: #dc2626;
  font-size: 12px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-documents__footer {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
  padding: 12px;
}

.kb-documents__hidden-input {
  display: none;
}

.kb-upload-dialog__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.kb-upload-dialog__title {
  margin: 0;
  color: #0f172a;
  font-size: 20px;
  font-weight: 700;
}

.kb-upload-dialog__subtitle {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 13px;
}

.kb-upload-dialog__target {
  display: flex;
  align-items: center;
  gap: 12px;
}

.kb-upload-dialog__target-label {
  color: #334155;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.kb-upload-dialog__target-select {
  width: 220px;
}

.kb-upload-dialog__body {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px;
}

.kb-upload-dropzone {
  border: 2px dashed #cbd5e1;
  border-radius: 20px;
  background: #fff;
  padding: 36px 24px;
  text-align: center;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease;
}

.kb-upload-dropzone.is-dragging {
  border-color: var(--admin-primary);
  background: var(--admin-primary-soft);
}

.kb-upload-dropzone__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 999px;
  background: var(--admin-primary-soft);
  color: var(--admin-primary);
}

.kb-upload-dropzone__title {
  margin: 16px 0 8px;
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}

.kb-upload-dropzone__hint {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.kb-upload-dropzone__actions {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  margin-top: 20px;
}

.kb-upload-queue {
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 20px;
  background: #ffffff;
}

.kb-upload-queue__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 16px 20px;
}

.kb-upload-queue__title {
  margin: 0;
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
}

.kb-upload-queue__table {
  display: flex;
  flex-direction: column;
  max-height: 360px;
  overflow: auto;
}

.kb-upload-queue__row {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr) minmax(0, 1.2fr) 96px 72px;
  align-items: center;
  gap: 16px;
  border-bottom: 1px solid #f1f5f9;
  padding: 14px 20px;
}

.kb-upload-queue__row--head {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #ffffff;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.kb-upload-queue__row:last-child {
  border-bottom: 0;
}

.kb-upload-queue__file {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  color: #0f172a;
  font-weight: 600;
}

.kb-upload-queue__file-name,
.kb-upload-queue__path {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-upload-queue__path {
  color: #64748b;
  font-family: Consolas, "SFMono-Regular", Monaco, monospace;
  font-size: 12px;
}

.kb-upload-queue__category {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid #bbf7d0;
  border-radius: 999px;
  background: #f0fdf4;
  color: #166534;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
}

.kb-upload-queue__category.is-plain {
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #475569;
}

.kb-upload-queue__category.is-new {
  border-color: #fde68a;
  background: #fffbeb;
  color: #b45309;
}

.kb-detail-drawer {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.kb-detail-drawer__title-block {
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 16px;
}

.kb-detail-drawer__title-block h3 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}

.kb-detail-drawer__title-block p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.kb-detail-drawer__meta,
.kb-detail-drawer__stats {
  display: grid;
  gap: 10px;
}

.kb-detail-drawer__meta div,
.kb-detail-drawer__stat {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  padding: 12px;
}

.kb-detail-drawer__meta span,
.kb-detail-drawer__stat span {
  color: #64748b;
  font-size: 13px;
}

.kb-detail-drawer__meta strong,
.kb-detail-drawer__stat strong {
  min-width: 0;
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
  text-align: right;
}

.is-right {
  text-align: right;
}

.kb-preview {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.kb-preview__meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.kb-preview__meta > div {
  display: flex;
  min-height: 84px;
  flex-direction: column;
  justify-content: center;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
  padding: 14px;
}

.kb-preview__label {
  color: #64748b;
  font-size: 12px;
}

.kb-preview__content {
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #ffffff;
  color: #0f172a;
  font-family: Consolas, "SFMono-Regular", Monaco, monospace;
  font-size: 13px;
  line-height: 1.75;
  margin: 0;
  padding: 18px;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 1280px) {
  .kb-detail-page__layout {
    grid-template-columns: 1fr;
  }

  .kb-sidebar {
    min-height: auto;
  }
}

@media (max-width: 900px) {
  .kb-sidebar__header {
    flex-direction: column;
    align-items: stretch;
  }

  .kb-documents__search,
  .kb-documents__status {
    width: 100%;
  }

  .kb-documents__status-filter {
    width: 100%;
  }

  .kb-preview__meta {
    grid-template-columns: 1fr;
  }

  .kb-upload-dialog__header,
  .kb-upload-dialog__footer,
  .kb-upload-dialog__target {
    flex-direction: column;
    align-items: stretch;
  }

  .kb-upload-dialog__target-select {
    width: 100%;
  }

  .kb-upload-queue__row {
    grid-template-columns: minmax(0, 1fr);
    gap: 10px;
  }

  .kb-upload-queue__row--head {
    display: none;
  }

  .is-right {
    text-align: left;
  }
}

@media (max-width: 640px) {
  .kb-detail-page__stats {
    grid-template-columns: 1fr;
  }
}
</style>
