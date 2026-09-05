import { Fragment } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

// `p` renders inline (no wrapping block) so a claim-citation pill sitting
// between two text blocks in the same sentence doesn't get pushed onto its
// own line — see PRISM_APP_INVENTORY bug report, "claim citations ... must
// not break line flow".
const components: Components = {
  p: ({ children }) => <Fragment>{children}</Fragment>,
  strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-brand underline hover:text-brand-hover"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-hairline pl-3 italic text-ink-secondary">
      {children}
    </blockquote>
  ),
  ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  code: ({ className, children, ...props }) => {
    const isBlock = /language-/.test(className ?? "");
    if (isBlock) {
      return (
        <code className={cn("font-mono text-xs", className)} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code className="rounded bg-surface-subtle px-1.5 py-0.5 font-mono text-xs text-ink" {...props}>
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-lg bg-ink p-3 text-white/90">{children}</pre>
  ),
};

export function ChatMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  );
}
