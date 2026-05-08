"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Boxes, Loader2, Plus, Search } from "lucide-react";
import { toast } from "sonner";

import { useTeamScope } from "@/components/team-scope/TeamScopeProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  productsApi,
  type ProductPayload,
  type ProductResponse,
} from "@/lib/api/products";
import {
  projectsApi,
  type ProjectPayload,
  type ProjectResponse,
} from "@/lib/api/endpoints/projects";
import { ProductDialog, type ProductFormState } from "../components/ProductDialog";
import { ProductSection } from "../components/ProductSection";
import { ProjectDialog, type ProjectFormState } from "../components/ProjectDialog";
import { buildProductProjectGroups } from "../lib/group-products";

const EMPTY_PRODUCT_FORM: ProductFormState = {
  name: "",
  code: "",
  description: "",
  is_active: true,
};

const EMPTY_PROJECT_FORM: ProjectFormState = {
  name: "",
  code: "",
  description: "",
  product_id: "",
  is_active: true,
};

function toProductForm(product: ProductResponse): ProductFormState {
  return {
    name: product.name,
    code: product.code,
    description: product.description ?? "",
    is_active: product.is_active,
  };
}

function toProjectForm(project: ProjectResponse): ProjectFormState {
  return {
    name: project.name,
    code: project.code,
    description: project.description ?? "",
    product_id: String(project.product_id),
    is_active: project.is_active,
  };
}

function toProductPayload(form: ProductFormState, teamId: number): ProductPayload {
  return {
    name: form.name.trim(),
    code: form.code.trim(),
    team_id: teamId,
    description: form.description.trim() || null,
    is_active: form.is_active,
  };
}

function toProjectPayload(form: ProjectFormState, teamId: number): ProjectPayload {
  return {
    name: form.name.trim(),
    code: form.code.trim(),
    team_id: teamId,
    product_id: Number(form.product_id),
    description: form.description.trim() || null,
    is_active: form.is_active,
  };
}

export default function ProductProjectWorkspacePage() {
  const { teamId, selectedTeam, teamsLoading } = useTeamScope();
  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingProduct, setSavingProduct] = useState(false);
  const [savingProject, setSavingProject] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedProductIds, setExpandedProductIds] = useState<number[]>([]);
  const [productDialogOpen, setProductDialogOpen] = useState(false);
  const [projectDialogOpen, setProjectDialogOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<ProductResponse | null>(null);
  const [editingProject, setEditingProject] = useState<ProjectResponse | null>(null);
  const [productForm, setProductForm] = useState<ProductFormState>(EMPTY_PRODUCT_FORM);
  const [projectForm, setProjectForm] = useState<ProjectFormState>(EMPTY_PROJECT_FORM);
  const [lockedProjectProductId, setLockedProjectProductId] = useState<string | undefined>(undefined);
  const loadErrorLabel = "加载产品和项目数据失败";
  const selectTeamLabel = "请先选择团队";
  const productNameRequiredLabel = "产品名称和编码不能为空";
  const productUpdatedLabel = "产品已更新";
  const productCreatedLabel = "产品已创建";
  const saveProductFailedLabel = "保存产品失败";
  const selectProductLabel = "请选择所属产品";
  const projectNameRequiredLabel = "项目名称和编码不能为空";
  const projectUpdatedLabel = "项目已更新";
  const projectCreatedLabel = "项目已创建";
  const saveProjectFailedLabel = "保存项目失败";
  const productDisabledLabel = "产品已停用";
  const productEnabledLabel = "产品已启用";
  const toggleProductFailedLabel = "切换产品状态失败";
  const projectDisabledLabel = "项目已停用";
  const projectEnabledLabel = "项目已启用";
  const toggleProjectFailedLabel = "切换项目状态失败";
  const productDeletedLabel = "产品已删除";
  const deleteProductFailedLabel = "删除产品失败";
  const projectDeletedLabel = "项目已删除";
  const deleteProjectFailedLabel = "删除项目失败";
  const loadingLabel = "正在加载产品项目数据...";
  const titleLabel = "产品项目工作台";
  const subtitlePrefix = "按产品查看项目和应用关系，项目详情页继续负责应用配置。";
  const currentTeamPrefix = "当前团队：";
  const createProductLabel = "新建产品";
  const searchPlaceholder = "搜索产品或项目名称、编码";
  const emptyProductsTitle = "当前团队还没有产品";
  const emptyProductsDescription =
    "请先创建产品，再在产品下创建项目。应用配置仍然在项目详情页完成。";
  const noMatchesTitle = "没有匹配的产品或项目";
  const noMatchesDescription = "可以调整搜索词后重试。";

  const loadWorkspace = useCallback(async () => {
    if (teamId == null) {
      setProducts([]);
      setProjects([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const [nextProducts, nextProjects] = await Promise.all([
        productsApi.list({ team_id: teamId }),
        projectsApi.list({ team_id: teamId }),
      ]);
      setProducts(nextProducts);
      setProjects(nextProjects);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : loadErrorLabel);
    } finally {
      setLoading(false);
    }
  }, [loadErrorLabel, teamId]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const groups = useMemo(
    () => buildProductProjectGroups({ products, projects, search: searchQuery }),
    [products, projects, searchQuery],
  );

  const hasSearch = searchQuery.trim().length > 0;

  useEffect(() => {
    if (hasSearch) {
      setExpandedProductIds(groups.map((group) => group.product.id));
      return;
    }

    setExpandedProductIds((current) => {
      const availableIds = new Set(groups.map((group) => group.product.id));
      const preserved = current.filter((id) => availableIds.has(id));
      if (preserved.length > 0) {
        return preserved;
      }
      const firstGroupWithProjects = groups.find((group) => group.projects.length > 0);
      return firstGroupWithProjects ? [firstGroupWithProjects.product.id] : [];
    });
  }, [groups, hasSearch]);

  const toggleExpanded = (productId: number) => {
    setExpandedProductIds((current) =>
      current.includes(productId)
        ? current.filter((item) => item !== productId)
        : [...current, productId],
    );
  };

  const openCreateProductDialog = () => {
    setEditingProduct(null);
    setProductForm(EMPTY_PRODUCT_FORM);
    setProductDialogOpen(true);
  };

  const openEditProductDialog = (product: ProductResponse) => {
    setEditingProduct(product);
    setProductForm(toProductForm(product));
    setProductDialogOpen(true);
  };

  const openCreateProjectDialog = (product?: ProductResponse) => {
    setEditingProject(null);
    const productId = product ? String(product.id) : "";
    setProjectForm({ ...EMPTY_PROJECT_FORM, product_id: productId });
    setLockedProjectProductId(productId || undefined);
    setProjectDialogOpen(true);
  };

  const openEditProjectDialog = (project: ProjectResponse) => {
    setEditingProject(project);
    setProjectForm(toProjectForm(project));
    setLockedProjectProductId(undefined);
    setProjectDialogOpen(true);
  };

  const saveProduct = async () => {
    if (teamId == null) {
      toast.error(selectTeamLabel);
      return;
    }
    if (!productForm.name.trim() || !productForm.code.trim()) {
      toast.error(productNameRequiredLabel);
      return;
    }

    setSavingProduct(true);
    try {
      const payload = toProductPayload(productForm, teamId);
      if (editingProduct) {
        await productsApi.update(editingProduct.id, payload);
        toast.success(productUpdatedLabel);
      } else {
        await productsApi.create(payload);
        toast.success(productCreatedLabel);
      }
      setProductDialogOpen(false);
      await loadWorkspace();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : saveProductFailedLabel);
    } finally {
      setSavingProduct(false);
    }
  };

  const saveProject = async () => {
    if (teamId == null) {
      toast.error(selectTeamLabel);
      return;
    }
    if (!projectForm.product_id) {
      toast.error(selectProductLabel);
      return;
    }
    if (!projectForm.name.trim() || !projectForm.code.trim()) {
      toast.error(projectNameRequiredLabel);
      return;
    }

    setSavingProject(true);
    try {
      const payload = toProjectPayload(projectForm, teamId);
      if (editingProject) {
        await projectsApi.update(editingProject.id, payload);
        toast.success(projectUpdatedLabel);
      } else {
        await projectsApi.create(payload);
        toast.success(projectCreatedLabel);
      }
      setProjectDialogOpen(false);
      await loadWorkspace();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : saveProjectFailedLabel);
    } finally {
      setSavingProject(false);
    }
  };

  const toggleProduct = async (product: ProductResponse) => {
    try {
      await productsApi.update(product.id, {
        name: product.name,
        code: product.code,
        team_id: product.team_id,
        description: product.description ?? null,
        is_active: !product.is_active,
      });
      toast.success(product.is_active ? productDisabledLabel : productEnabledLabel);
      await loadWorkspace();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : toggleProductFailedLabel);
    }
  };

  const toggleProject = async (project: ProjectResponse) => {
    try {
      await projectsApi.update(project.id, {
        name: project.name,
        code: project.code,
        team_id: project.team_id,
        product_id: project.product_id,
        description: project.description ?? null,
        is_active: !project.is_active,
      });
      toast.success(project.is_active ? projectDisabledLabel : projectEnabledLabel);
      await loadWorkspace();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : toggleProjectFailedLabel);
    }
  };

  const deleteProduct = async (product: ProductResponse) => {
    if (
      !window.confirm(
        `确认删除产品“${product.name}”吗？`,
      )
    ) {
      return;
    }

    try {
      await productsApi.delete(product.id);
      toast.success(productDeletedLabel);
      await loadWorkspace();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : deleteProductFailedLabel);
    }
  };

  const deleteProject = async (project: ProjectResponse) => {
    if (
      !window.confirm(
        `确认删除项目“${project.name}”吗？项目下的应用也会一并删除。`,
      )
    ) {
      return;
    }

    try {
      await projectsApi.delete(project.id);
      toast.success(projectDeletedLabel);
      await loadWorkspace();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : deleteProjectFailedLabel);
    }
  };

  if (loading || teamsLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-500">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        {loadingLabel}
      </div>
    );
  }

  if (teamId == null) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-500">
        {selectTeamLabel}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-slate-50">
      <div className="border-b border-slate-200 bg-white px-8 py-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">{titleLabel}</h1>
            <p className="mt-1 text-sm text-slate-500">
              {subtitlePrefix}
              {selectedTeam ? ` ${currentTeamPrefix}${selectedTeam.name}` : ""}
            </p>
          </div>
          <Button onClick={openCreateProductDialog} className="gap-2 bg-blue-600 hover:bg-blue-700">
            <Plus className="h-4 w-4" />
            {createProductLabel}
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex flex-wrap items-center gap-4">
          <div className="relative w-full max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              placeholder={searchPlaceholder}
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              className="h-10 border-slate-200 bg-white pl-9"
            />
          </div>
        </div>

        {products.length === 0 ? (
          <div className="flex min-h-[420px] items-center justify-center">
            <div className="w-full max-w-md rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center shadow-sm">
              <Boxes className="mx-auto h-12 w-12 text-slate-300" />
              <h2 className="mt-4 text-lg font-semibold text-slate-900">{emptyProductsTitle}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                {emptyProductsDescription}
              </p>
              <Button
                onClick={openCreateProductDialog}
                className="mt-6 gap-2 bg-blue-600 hover:bg-blue-700"
              >
                <Plus className="h-4 w-4" />
                {createProductLabel}
              </Button>
            </div>
          </div>
        ) : groups.length === 0 ? (
          <div className="flex min-h-[320px] items-center justify-center">
            <div className="text-center">
              <h2 className="text-base font-semibold text-slate-900">{noMatchesTitle}</h2>
              <p className="mt-2 text-sm text-slate-500">{noMatchesDescription}</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {groups.map((group) => (
              <ProductSection
                key={group.product.id}
                product={group.product}
                projects={group.projects}
                totalApps={group.totalApps}
                expanded={expandedProductIds.includes(group.product.id)}
                searchActive={hasSearch}
                onToggleExpanded={() => toggleExpanded(group.product.id)}
                onCreateProject={openCreateProjectDialog}
                onEditProduct={openEditProductDialog}
                onToggleProduct={(product) => void toggleProduct(product)}
                onDeleteProduct={(product) => void deleteProduct(product)}
                onEditProject={openEditProjectDialog}
                onToggleProject={(project) => void toggleProject(project)}
                onDeleteProject={(project) => void deleteProject(project)}
              />
            ))}
          </div>
        )}
      </div>

      <ProductDialog
        open={productDialogOpen}
        title={editingProduct ? "编辑产品" : "新建产品"}
        form={productForm}
        saving={savingProduct}
        onOpenChange={setProductDialogOpen}
        onChange={setProductForm}
        onSubmit={() => void saveProduct()}
      />

      <ProjectDialog
        open={projectDialogOpen}
        title={editingProject ? "编辑项目" : "新建项目"}
        form={projectForm}
        products={products}
        saving={savingProject}
        lockProductId={lockedProjectProductId}
        onOpenChange={(open) => {
          setProjectDialogOpen(open);
          if (!open) {
            setLockedProjectProductId(undefined);
          }
        }}
        onChange={setProjectForm}
        onSubmit={() => void saveProject()}
      />
    </div>
  );
}
