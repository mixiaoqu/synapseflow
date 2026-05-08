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

export interface ProductFormState {
  name: string;
  code: string;
  description: string;
  is_active: boolean;
}

interface ProductDialogProps {
  open: boolean;
  title: string;
  form: ProductFormState;
  saving: boolean;
  onOpenChange: (open: boolean) => void;
  onChange: (next: ProductFormState) => void;
  onSubmit: () => void;
}

export function ProductDialog(props: ProductDialogProps) {
  const { open, title, form, saving, onOpenChange, onChange, onSubmit } = props;
  const description = "产品是项目的上级业务单元，用于承载一组相关项目。";
  const productNameLabel = "产品名称";
  const productCodeLabel = "产品编码";
  const descriptionLabel = "描述";
  const productNamePlaceholder = "例如：智能知识库";
  const productCodePlaceholder = "例如：smart_kb";
  const descriptionPlaceholder = "说明产品定位、适用团队或业务范围";
  const activeLabel = "启用产品";
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
            <label className="text-sm font-medium text-slate-700">{productNameLabel}</label>
            <Input
              value={form.name}
              onChange={(event) => onChange({ ...form, name: event.target.value })}
              placeholder={productNamePlaceholder}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium text-slate-700">{productCodeLabel}</label>
            <Input
              value={form.code}
              onChange={(event) => onChange({ ...form, code: event.target.value })}
              placeholder={productCodePlaceholder}
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
