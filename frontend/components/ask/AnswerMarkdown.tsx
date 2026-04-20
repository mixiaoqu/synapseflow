import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";

export function AnswerMarkdown({ text }: { text: string }) {
  return (
    <div className="text-[15px] leading-7 text-slate-800 selection:bg-teal-100 selection:text-slate-900">
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
          ul: ({ children }) => (
            <ul className="mb-3 list-disc pl-5 space-y-1.5 last:mb-0 marker:text-teal-600">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-3 list-decimal pl-5 space-y-1.5 last:mb-0">
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
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
