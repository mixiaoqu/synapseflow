import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

export function AnswerMarkdown({ text }: { text: string }) {
  return (
    <div className="text-[15px] leading-7 text-slate-800 selection:bg-teal-100 selection:text-slate-900">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
          ul: ({ children }) => (
            <ul className="mb-3 list-disc space-y-1.5 pl-5 marker:text-teal-600 last:mb-0">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-3 list-decimal space-y-1.5 pl-5 last:mb-0">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold text-slate-900">{children}</strong>
          ),
          pre: ({ children }) => (
            <pre className="my-2 overflow-x-auto rounded-xl border border-slate-700/50 bg-slate-900 p-3.5 text-[13px] font-mono text-slate-100">
              {children}
            </pre>
          ),
          code: ({ className, children, ...props }) => {
            const block = Boolean(className);
            if (block) {
              return (
                <code className={cn("font-mono text-inherit", className)} {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code
                className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[13px] font-mono text-slate-800"
                {...props}
              >
                {children}
              </code>
            );
          },
          h1: ({ children }) => (
            <h3 className="mt-4 mb-2 text-base font-semibold text-slate-900 first:mt-0">
              {children}
            </h3>
          ),
          h2: ({ children }) => (
            <h3 className="mt-4 mb-2 text-base font-semibold text-slate-900 first:mt-0">
              {children}
            </h3>
          ),
          h3: ({ children }) => (
            <h3 className="mt-3 mb-1.5 text-sm font-semibold text-slate-900">
              {children}
            </h3>
          ),
          table: ({ children }) => (
            <div className="my-4 overflow-hidden rounded-xl border border-slate-200">
              <Table className="min-w-full text-[13px] leading-6">{children}</Table>
            </div>
          ),
          thead: ({ children }) => <TableHeader className="bg-slate-50">{children}</TableHeader>,
          tbody: ({ children }) => <TableBody>{children}</TableBody>,
          tr: ({ children }) => <TableRow>{children}</TableRow>,
          th: ({ children }) => (
            <TableHead className="h-auto px-3 py-2 text-[12px] normal-case tracking-normal text-slate-600">
              {children}
            </TableHead>
          ),
          td: ({ children }) => <TableCell className="px-3 py-2 text-slate-700">{children}</TableCell>,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
