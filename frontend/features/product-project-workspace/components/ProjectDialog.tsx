"use client";

import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { ProductResponse } from "@/lib/api/products";

export interface ProjectFormState {
  name: string;
  code: string;
  description: string;
  product_id: string;
  is_active: boolean;
}

interface ProjectDialogProps {
  open: boolean;
  title: string;
  form: ProjectFormState;
  products: ProductResponse[];
  saving: boolean;
  lockProductId?: string;
  onOpenChange: (open: boolean) => void;
  onChange: (next: ProjectFormState) => void;
  onSubmit: () => void;
}

export function ProjectDialog(props: ProjectDialogProps) {
  const {
    open,
    title,
    form,
    products,
    saving,
    lockProductId,
    onOpenChange,
    onChange,
    onSubmit,
  } = props;
  const description = "项目用于承接具体业务系统，应用配置仍在项目详情页完成。";
  const productLabel = "所属产品";
  const selectProductLabel = "请选择产品";
  const projectNameLabel = "项目名称";
  const projectCodeLabel = "项目编码";
  const descriptionLabel = "描述";
  const projectNamePlaceholder = "例如：生产环境";
  const projectCodePlaceholder = "例如：production";
  const descriptionPlaceholder = "说明项目对应的业务系统或使用场景";
  const activeLabel = "启用项目";
  const cancelLabel = "取消";
  const saveLabel = "保存";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="grid gap-2">
            <label className="text-sm font-medium text-slate-700">{productLabel}</label>
            <select
              value={form.product_id}
              disabled={Boolean(lockProductId)}
              onChange={(event) => onChange({ ...form, product_id: event.target.value })}
              className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50 disabled:cursor-not-allowed disabled:bg-slate-50"
            >
              <option value="">{selectProductLabel}</option>
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name} ({product.code})
                </option>
              ))}
            </select>
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium text-slate-700">{projectNameLabel}</label>
            <Input
              value={form.name}
              onChange={(event) => onChange({ ...form, name: event.target.value })}
              placeholder={projectNamePlaceholder}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium text-slate-700">{projectCodeLabel}</label>
            <Input
              value={form.code}
              onChange={(event) => onChange({ ...form, code: event.target.value })}
              placeholder={projectCodePlaceholder}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium text-slate-700">{descriptionLabel}</label>
            <Textarea
              value={form.description}
              onChange={(event) => onChange({ ...form, description: event.target.value })}
              placeholder={descriptionPlaceholder}
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <Checkbox
              checked={form.is_active}
              onCheckedChange={(checked) => onChange({ ...form, is_active: checked })}
            />
            {activeLabel}
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              {cancelLabel}
            </Button>
            <Button onClick={onSubmit} disabled={saving}>
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {saveLabel}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
