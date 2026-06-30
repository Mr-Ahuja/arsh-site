import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { MermaidBlock } from "./MermaidBlock";

// ── Element-level components using our design tokens ─────────────────────────

const components: Components = {
  h1: ({ children }) => (
    <h1 className="mb-4 mt-8 border-b border-line pb-2 text-lg font-bold text-ink first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-3 mt-6 border-b border-line pb-1 text-base font-semibold text-ink">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-2 mt-5 text-sm font-semibold text-ink">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="mb-1 mt-4 text-xs font-semibold uppercase tracking-wide text-ink-muted">
      {children}
    </h4>
  ),
  p: ({ children }) => (
    <p className="mb-4 text-sm leading-relaxed text-ink-soft">{children}</p>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-brand underline underline-offset-2 hover:opacity-80"
    >
      {children}
    </a>
  ),
  ul: ({ children }) => (
    <ul className="mb-4 list-disc space-y-1 pl-5 text-sm text-ink-soft">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-4 list-decimal space-y-1 pl-5 text-sm text-ink-soft">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-6">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="my-4 border-l-4 border-brand pl-4 text-sm italic text-ink-muted">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-6 border-line" />,
  strong: ({ children }) => (
    <strong className="font-semibold text-ink">{children}</strong>
  ),
  em: ({ children }) => <em className="italic text-ink-soft">{children}</em>,

  // Tables
  table: ({ children }) => (
    <div className="my-4 overflow-x-auto rounded border border-line">
      <table className="w-full text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-surface-alt">{children}</thead>,
  th: ({ children }) => (
    <th className="border-b border-line px-3 py-2 text-left font-semibold text-ink">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-b border-line px-3 py-2 text-ink-soft last:border-b-0">
      {children}
    </td>
  ),
  tr: ({ children }) => (
    <tr className="hover:bg-surface-hover last:border-b-0">{children}</tr>
  ),

  // Code — inline vs block detected by presence of language- className
  // Override `pre` to a passthrough so code block renders its own wrapper.
  pre: ({ children }) => <>{children}</>,

  code({ className, children }) {
    const language = /language-(\w+)/.exec(className ?? "")?.[1] ?? "";
    const code = String(children).replace(/\n$/, "");

    if (language === "mermaid") {
      return <MermaidBlock code={code} />;
    }

    if (language) {
      // Fenced code block
      return (
        <div className="group relative my-4">
          {language && (
            <span className="absolute right-2 top-2 text-2xs text-ink-muted opacity-60">
              {language}
            </span>
          )}
          <pre className="overflow-x-auto rounded border border-line bg-surface-alt px-4 py-3 text-xs leading-5">
            <code className="font-mono text-ink">{code}</code>
          </pre>
        </div>
      );
    }

    // Inline code
    return (
      <code className="rounded bg-surface-hover px-1 py-0.5 font-mono text-xs text-brand">
        {children}
      </code>
    );
  },
};

// ── Public component ──────────────────────────────────────────────────────────

export function MarkdownViewer({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  );
}
