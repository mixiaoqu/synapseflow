"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Box, Edit, Loader2, MoreHorizontal, Plus, Search, Settings, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { useTeamScope } from "@/components/team-scope/TeamScopeProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { productsApi, type ProductPayload, type ProductResponse } from "@/lib/api/products";

interface ProductFormState {
  name: string;
  code: string;
  description: string;
  is_active: boolean;
}

const EMPTY_FORM: ProductFormState = {
  name: "",
  code: "",
  description: "",
  is_active: true,
};

function toForm(product: ProductResponse): ProductFormState {
  return {
    name: product.name,
    code: product.code,
    description: product.description ?? "",
    is_active: product.is_active,
  };
}

function toPayload(form: ProductFormState, teamId: number): ProductPayload {
  return {
    name: form.name.trim(),
    code: form.code.trim(),
    team_id: teamId,
    description: form.description.trim() || null,
    is_active: form.is_active,
  };
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

export default function ProductsPage() {
  const { teamId, selectedTeam, teamsLoading } = useTeamScope();
  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<ProductResponse | null>(null);
  const [form, setForm] = useState<ProductFormState>(EMPTY_FORM);

  const loadProducts = useCallback(async () => {
    if (teamId == null) {
      setProducts([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      setProducts(await productsApi.list({ team_id: teamId }));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load products");
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    void loadProducts();
  }, [loadProducts]);

  const filteredProducts = useMemo(() => {
    const keyword = searchQuery.trim().toLowerCase();
    if (!keyword) return products;
    return products.filter(
      (product) =>
        product.name.toLowerCase().includes(keyword) ||
        product.code.toLowerCase().includes(keyword) ||
        (product.description ?? "").toLowerCase().includes(keyword),
    );
  }, [products, searchQuery]);

  const openCreateDialog = () => {
    setEditingProduct(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  };

  const openEditDialog = (product: ProductResponse) => {
    setEditingProduct(product);
    setForm(toForm(product));
    setDialogOpen(true);
  };

  const saveProduct = async () => {
    if (teamId == null) {
      toast.error("请先选择团队");
      return;
    }
    if (!form.name.trim() || !form.code.trim()) {
      toast.error("产品名称和编码不能为空");
      return;
    }

    setSaving(true);
    try {
      const payload = toPayload(form, teamId);
      if (editingProduct) {
        await productsApi.update(editingProduct.id, payload);
        toast.success("产品已更新");
      } else {
        await productsApi.create(payload);
        toast.success("产品已创建");
      }
      setDialogOpen(false);
      await loadProducts();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存产品失败");
    } finally {
      setSaving(false);
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
      toast.success(product.is_active ? "产品已停用" : "产品已启用");
      await loadProducts();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "切换产品状态失败");
    }
  };

  const deleteProduct = async (product: ProductResponse) => {
    if (!window.confirm(`确认删除产品“${product.name}”吗？`)) return;
    try {
      await productsApi.delete(product.id);
      toast.success("产品已删除");
      await loadProducts();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "删除产品失败");
    }
  };

  const noTeam = !teamsLoading && teamId == null;

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 bg-white px-8 py-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">产品管理</h1>
            <p className="mt-1 text-sm text-slate-500">
              管理团队下的标准产品，并在项目中复用这些产品。
              {selectedTeam ? ` 当前团队：${selectedTeam.name}` : ""}
            </p>
          </div>
          <Button
            onClick={openCreateDialog}
            disabled={teamId == null}
            className="gap-2 bg-blue-600 hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            新建产品
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center gap-4">
          <div className="relative w-72">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              placeholder="搜索产品名称或编码..."
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              className="h-10 border-slate-200 pl-9"
            />
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="grid grid-cols-12 gap-4 border-b border-slate-100 bg-slate-50/50 px-6 py-3 text-sm font-medium text-slate-500">
            <div className="col-span-3">产品名称</div>
            <div className="col-span-2">产品编码</div>
            <div className="col-span-2 text-center">项目数</div>
            <div className="col-span-2">状态</div>
            <div className="col-span-1">创建时间</div>
            <div className="col-span-2 text-right">操作</div>
          </div>

          {loading || teamsLoading ? (
            <div className="flex h-64 items-center justify-center text-sm text-slate-500">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              正在加载产品...
            </div>
          ) : noTeam ? (
            <div className="py-12 text-center">
              <Box className="mx-auto h-12 w-12 text-slate-200" />
              <h3 className="mt-4 text-sm font-medium text-slate-900">请先选择团队</h3>
            </div>
          ) : filteredProducts.length === 0 ? (
            <div className="py-12 text-center">
              <Box className="mx-auto h-12 w-12 text-slate-200" />
              <h3 className="mt-4 text-sm font-medium text-slate-900">暂无产品</h3>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {filteredProducts.map((product) => (
                <div
                  key={product.id}
                  className="grid grid-cols-12 items-center gap-4 px-6 py-4 transition-colors hover:bg-slate-50/50"
                >
                  <div className="col-span-3 flex flex-col">
                    <span className="font-medium text-slate-900">{product.name}</span>
                    <span className="mt-0.5 truncate pr-4 text-xs text-slate-500">
                      {product.description || "未填写描述"}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <code className="rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-600">
                      {product.code}
                    </code>
                  </div>
                  <div className="col-span-2 text-center">
                    <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-slate-100 px-2 text-xs font-medium text-slate-600">
                      {product.project_count}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <Badge
                      variant={product.is_active ? "default" : "secondary"}
                      className={product.is_active ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-50" : ""}
                    >
                      {product.is_active ? "已启用" : "已停用"}
                    </Badge>
                  </div>
                  <div className="col-span-1 text-sm text-slate-500">{formatDate(product.created_at)}</div>
                  <div className="col-span-2 flex justify-end gap-2">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-500">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-36">
                        <DropdownMenuItem onSelect={() => openEditDialog(product)}>
                          <Edit className="mr-2 h-4 w-4 text-slate-400" />
                          编辑
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => void toggleProduct(product)}>
                          <Settings className="mr-2 h-4 w-4 text-slate-400" />
                          {product.is_active ? "停用" : "启用"}
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-red-600 focus:text-red-600"
                          onSelect={() => void deleteProduct(product)}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          删除
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle>{editingProduct ? "编辑产品" : "新建产品"}</DialogTitle>
            <DialogDescription>产品是项目的上级业务单元。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid gap-2">
              <label className="text-sm font-medium text-slate-700">产品名称</label>
              <Input
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="例如：Smart KB"
              />
            </div>
            <div className="grid gap-2">
              <label className="text-sm font-medium text-slate-700">产品编码</label>
              <Input
                value={form.code}
                onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))}
                placeholder="例如：smart_kb"
              />
            </div>
            <div className="grid gap-2">
              <label className="text-sm font-medium text-slate-700">描述</label>
              <Textarea
                value={form.description}
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="产品定位或适用场景"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
                className="h-4 w-4 rounded border-slate-300"
              />
              启用产品
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                取消
              </Button>
              <Button onClick={() => void saveProduct()} disabled={saving}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                保存
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
