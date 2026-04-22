"use client";

import { Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import {
  actionButtonClass,
  reviewActionMeta,
  type ReviewAction,
} from "./review-utils";

interface BatchActionBarProps {
  selectedCount: number;
  visibleActions: ReviewAction[];
  enabledActions: ReviewAction[];
  runningAction: ReviewAction | null;
  disableReason?: string | null;
  onRunAction: (action: ReviewAction) => void;
  onClearSelection: () => void;
}

export function BatchActionBar({
  selectedCount,
  visibleActions,
  enabledActions,
  runningAction,
  disableReason,
  onRunAction,
  onClearSelection,
}: BatchActionBarProps) {
  const enabledSet = new Set(enabledActions);

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-sm font-medium text-slate-900">
            已选择 {selectedCount} 项
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {disableReason || "可执行的批量操作会显示在右侧。"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {visibleActions.length === 0 ? (
            <span className="text-sm text-slate-400">当前选择暂时没有可执行的批量动作。</span>
          ) : (
            visibleActions.map((action) => {
              const disabled = !enabledSet.has(action) || runningAction != null;

              return (
                <Button
                  key={action}
                  type="button"
                  disabled={disabled}
                  onClick={() => onRunAction(action)}
                  className={cn(
                    "h-10 rounded-xl px-4 text-sm shadow-none",
                    actionButtonClass(action),
                    disabled && "opacity-50",
                  )}
                >
                  {runningAction === action ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      处理中
                    </>
                  ) : (
                    reviewActionMeta[action].batchLabel
                  )}
                </Button>
              );
            })
          )}

          <Button
            type="button"
            variant="ghost"
            onClick={onClearSelection}
            className="h-10 rounded-xl px-3 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="h-4 w-4" />
            清空选择
          </Button>
        </div>
      </div>
    </div>
  );
}
