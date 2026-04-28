import { type ReactNode } from "react";

import { cn } from "@/lib/utils";

export function AdminPage({
  children,
  className,
  wide = false,
}: {
  children: ReactNode;
  className?: string;
  wide?: boolean;
}) {
  return (
    <div className={cn("px-6 py-6 sm:px-8", className)}>
      <div className={cn("mx-auto space-y-6", wide ? "max-w-[1700px]" : "max-w-[1440px]")}>
        {children}
      </div>
    </div>
  );
}

export function AdminPageHeader({
  title,
  description,
  eyebrow,
  actions,
}: {
  title: string;
  description?: string;
  eyebrow?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description ? (
          <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-500">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function AdminPageContent({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn("rounded-2xl border border-slate-200 bg-white shadow-sm", className)}
    >
      {children}
    </section>
  );
}
