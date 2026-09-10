import { useMemo } from "react";
import ReactMarkdown, { defaultUrlTransform, type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import { VerdictPill } from "@/components/VerdictPill";
import { claimLabelToVerdict } from "@/lib/claimMeta";
import type { ClaimLabel } from "@/types/api";

// Citations and the streaming cursor are threaded through the markdown
// source itself as image nodes (`![](cite:<id>)` / `![](cursor:1)`) rather
// than raw HTML: react-markdown only turns embedded HTML into real elements
// with the rehype-raw plugin, which would also let any stray HTML the LLM
// emits (accidental, or coaxed by adversarial paper content) render as live
// DOM. Image syntax is parsed natively by remark with no extra plugin, and
// the sentinel schemes below are the only ones exempted from react-markdown's
// default link/image sanitizer - genuine http(s)/mailto links from the LLM
// still go through normal sanitization.
const CITE_PREFIX = "cite:";
const CURSOR_MARKER = "cursor:1";

export function citeMarker(claimId: string): string {
  return `![](${CITE_PREFIX}${claimId})`;
}

export function cursorMarker(): string {
  return `![](${CURSOR_MARKER})`;
}

function chatUrlTransform(url: string): string {
  if (url.startsWith(CITE_PREFIX) || url === CURSOR_MARKER) return url;
  return defaultUrlTransform(url);
}

export interface ChatCiteInfo {
  claim_summary: string;
  display_label: ClaimLabel;
}

interface ChatMarkdownProps {
  content: string;
  claimsById?: Record<string, ChatCiteInfo>;
  onClaimClick?: (claimId: string) => void;
}

export function ChatMarkdown({ content, claimsById, onClaimClick }: ChatMarkdownProps) {
  const components = useMemo<Components>(
    () => ({
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
      ul: ({ children }) => <ul className="my-1 list-disc space-y-0.5 pl-5">{children}</ul>,
      ol: ({ children }) => <ol className="my-1 list-decimal space-y-0.5 pl-5">{children}</ol>,
      li: ({ children }) => <li className="leading-[1.45]">{children}</li>,
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
      img: ({ src }) => {
        if (src === CURSOR_MARKER) return <span className="streaming-cursor" />;

        if (typeof src === "string" && src.startsWith(CITE_PREFIX)) {
          const claimId = src.slice(CITE_PREFIX.length);
          const claim = claimsById?.[claimId];
          // Orphaned citation (id not in this turn's retrieved claims) -
          // drop it silently rather than showing a broken pill.
          if (!claim) return null;
          return (
            <button
              type="button"
              onClick={() => onClaimClick?.(claimId)}
              title={claim.claim_summary}
              className="mx-0.5 inline-flex items-center align-middle transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-subtle rounded-full"
            >
              <VerdictPill verdict={claimLabelToVerdict[claim.display_label]} size="xs" />
            </button>
          );
        }

        // No genuine images are expected in chat answers (the LLM only
        // answers from paper text/claims) - drop anything else rather than
        // hotlinking an LLM-hallucinated image URL.
        return null;
      },
    }),
    [claimsById, onClaimClick]
  );

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} urlTransform={chatUrlTransform}>
      {content}
    </ReactMarkdown>
  );
}
