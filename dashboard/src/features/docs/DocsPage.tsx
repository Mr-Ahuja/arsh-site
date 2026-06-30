import { useEffect, useState } from "react";
import { NavLink, Navigate, useParams } from "react-router-dom";
import { DOCS } from "./docsManifest";
import { MarkdownViewer } from "./MarkdownViewer";

function Sidebar({ activeSlug }: { activeSlug: string }) {
  return (
    <nav className="w-52 shrink-0 border-r border-line bg-surface">
      <div className="px-4 py-3">
        <h2 className="text-2xs font-semibold uppercase tracking-widest text-ink-muted">Docs</h2>
      </div>
      <ul>
        {DOCS.map((doc) => (
          <li key={doc.slug}>
            <NavLink
              to={`/docs/${doc.slug}`}
              className={`block px-4 py-2 text-xs transition-colors ${
                activeSlug === doc.slug
                  ? "bg-brand-bg font-medium text-brand"
                  : "text-ink-soft hover:bg-surface-hover"
              }`}
            >
              {doc.title}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function DocContent({ slug }: { slug: string }) {
  const doc = DOCS.find((d) => d.slug === slug);
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!doc) return;
    setLoading(true);
    setContent(null);
    setError(null);

    fetch(doc.file)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      .then((text) => {
        setContent(text);
        setLoading(false);
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Failed to load");
        setLoading(false);
      });
  }, [doc]);

  if (!doc) {
    return (
      <div className="p-8 text-sm text-ink-muted">
        Page not found.{" "}
        <NavLink to="/docs/getting-started" className="text-brand underline">
          Go to Getting Started
        </NavLink>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-8 text-sm text-ink-muted">Loading…</div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-sm text-neg">
        Could not load doc: {error}
      </div>
    );
  }

  return (
    <article className="mx-auto max-w-3xl px-8 py-6">
      <MarkdownViewer content={content ?? ""} />
    </article>
  );
}

export function DocsPage() {
  const { slug } = useParams<{ slug?: string }>();

  // /docs with no slug → redirect to first doc
  if (!slug) {
    return <Navigate to={`/docs/${DOCS[0].slug}`} replace />;
  }

  return (
    // h-full fills the <main> which is already a flex child with overflow-y-auto.
    // The inner scroll container gets its own overflow so the sidebar stays fixed.
    <div className="flex" style={{ height: "100%" }}>
      <Sidebar activeSlug={slug} />
      <div className="min-w-0 flex-1 overflow-y-auto">
        <DocContent slug={slug} />
      </div>
    </div>
  );
}
