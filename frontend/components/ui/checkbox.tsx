"use client";

import * as React from "react";
import { Check, Minus } from "lucide-react";

import { cn } from "@/lib/utils";

type CheckedState = boolean | "indeterminate";

export interface CheckboxProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onChange"> {
  checked?: CheckedState;
  onCheckedChange?: (checked: boolean) => void;
}

export const Checkbox = React.forwardRef<HTMLButtonElement, CheckboxProps>(
  ({ className, checked = false, disabled, onCheckedChange, ...props }, ref) => {
    const isChecked = checked === true;
    const isIndeterminate = checked === "indeterminate";

    return (
      <button
        ref={ref}
        type="button"
        role="checkbox"
        aria-checked={isIndeterminate ? "mixed" : isChecked}
        disabled={disabled}
        data-state={isChecked || isIndeterminate ? "checked" : "unchecked"}
        onClick={() => {
          if (disabled) return;
          onCheckedChange?.(!isChecked);
        }}
        className={cn(
          "inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border border-slate-300 bg-white text-slate-900 shadow-sm transition hover:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-slate-900 data-[state=checked]:bg-slate-900 data-[state=checked]:text-white",
          className,
        )}
        {...props}
      >
        {isIndeterminate ? (
          <Minus className="h-3.5 w-3.5" />
        ) : isChecked ? (
          <Check className="h-3.5 w-3.5" />
        ) : null}
      </button>
    );
  },
);

Checkbox.displayName = "Checkbox";
