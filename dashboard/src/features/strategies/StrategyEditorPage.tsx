import { lazy, Suspense, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost, type ApiError } from "../../lib/api";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { useUiStore } from "../../stores/uiStore";

// Monaco is heavy — load it only when this page mounts (own chunk).
const MonacoEditor = lazy(() =>
  import("@monaco-editor/react").then((m) => ({ default: m.default })),
);

interface ValidateResult {
  ok: boolean;
  errors: { type: string; line?: number; message: string }[];
  strategies: string[];
}

const STARTER = `"""My strategy — describe what it does here."""

from __future__ import annotations

from engine.data.types import TickData
from engine.strategy import BaseStrategy, Position, StrategyOrder


class Strategy(BaseStrategy):
    instrument = "NSE:SBIN"
    timeframe = "5minute"
    params: dict = {"qty": 10}
    param_schema = {"qty": {"type": int, "min": 1}}

    def on_start(self) -> None:
        pass

    def entry(self, tick: TickData) -> StrategyOrder | None:
        # Return self.buy(...) or self.sell(...) to open a position, or None.
        return None

    def on_tick(self, tick: TickData, pos: Position) -> None:
        pos.vars["peak"] = max(pos.vars.get("peak", tick.ltp), tick.ltp)

    def exit(self, tick: TickData, pos: Position) -> bool:
        return tick.ltp <= pos.vars.get("peak", 0.0) * 0.99
`;

// ── File list ───────────────────────────────────────────────────────────────────

function FileList({
  files,
  active,
  onSelect,
  onNew,
}: {
  files: string[];
  active: string | null;
  onSelect: (f: string) => void;
  onNew: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-2xs font-semibold uppercase tracking-wide text-ink-muted">
          Strategy files
        </span>
        <Button size="sm" variant="ghost" onClick={onNew}>
          + New
        </Button>
      </div>
      <div className="space-y-0.5 overflow-y-auto">
        {files.map((f) => (
          <button
            key={f}
            onClick={() => onSelect(f)}
            className={`w-full truncate rounded px-2.5 py-1.5 text-left font-mono text-xs transition-colors ${
              active === f
                ? "bg-brand-bg text-brand"
                : "text-ink-soft hover:bg-surface-hover"
            }`}
          >
            {f}
          </button>
        ))}
        {!files.length && <p className="px-1 text-xs text-ink-muted">No strategies yet.</p>}
      </div>
    </div>
  );
}

// ── Validation output ─────────────────────────────────────────────────────────

function ValidationPanel({ result }: { result: ValidateResult | null }) {
  if (!result) return null;
  if (result.ok) {
    return (
      <div className="rounded border border-pos/40 bg-pos-bg px-3 py-2 text-xs text-pos">
        ✓ Valid. Runnable: {result.strategies.map((s) => <code key={s} className="mx-1">{s}</code>)}
      </div>
    );
  }
  return (
    <div className="rounded border border-neg/40 bg-neg-bg px-3 py-2 text-xs text-neg">
      {result.errors.map((e, i) => (
        <div key={i} className="font-mono">
          {e.type}
          {e.line != null ? ` (line ${e.line})` : ""}: {e.message}
        </div>
      ))}
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────────

export function StrategyEditorPage() {
  const qc = useQueryClient();
  const theme = useUiStore((s) => s.theme);
  const [active, setActive] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [newName, setNewName] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidateResult | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const { data: filesData } = useQuery({
    queryKey: ["strategy-files"],
    queryFn: () => apiGet<{ files: string[] }>("/strategies/files"),
  });
  const files = filesData?.files ?? [];

  // Load source when the active file changes (and it's an existing file).
  const { data: source } = useQuery({
    queryKey: ["strategy-source", active],
    queryFn: () => apiGet<{ file: string; content: string }>(`/strategies/source?file=${active}`),
    enabled: !!active && active !== newName,
  });
  useEffect(() => {
    if (source) setDraft(source.content);
  }, [source]);

  // Auto-select the first file on load.
  useEffect(() => {
    if (!active && !newName && files.length) setActive(files[0]);
  }, [files, active, newName]);

  const validate = useMutation({
    mutationFn: (body: object) => apiPost<ValidateResult>("/strategies/validate", body),
    onSuccess: (r) => setValidation(r),
  });

  const save = useMutation({
    mutationFn: (body: { file: string; content: string }) =>
      apiPost<ValidateResult & { file: string; saved: boolean }>("/strategies/source", body),
    onSuccess: (r) => {
      setValidation({ ok: r.ok, errors: r.errors, strategies: r.strategies });
      setNotice(`Saved ${r.file}`);
      setNewName(null);
      qc.invalidateQueries({ queryKey: ["strategy-files"] });
      qc.invalidateQueries({ queryKey: ["strategies"] }); // backtest form dropdown
      setActive(r.file);
    },
    onError: (e: ApiError) => setNotice(e.message),
  });

  const remove = useMutation({
    mutationFn: (file: string) => apiDelete(`/strategies/source?file=${file}`),
    onSuccess: () => {
      setNotice(`Deleted ${active}`);
      setActive(null);
      setDraft("");
      qc.invalidateQueries({ queryKey: ["strategy-files"] });
    },
    onError: (e: ApiError) => setNotice(e.message),
  });

  function handleNew() {
    const name = prompt("New strategy filename (e.g. my_strategy.py):");
    if (!name) return;
    const file = name.endsWith(".py") ? name : `${name}.py`;
    setNewName(file);
    setActive(file);
    setDraft(STARTER);
    setValidation(null);
    setNotice(null);
  }

  function handleSave() {
    if (!active) return;
    save.mutate({ file: active, content: draft });
  }

  function handleValidate() {
    validate.mutate({ content: draft, ...(active && active !== newName ? { file: active } : {}) });
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-ink">Strategy Editor</h1>
          <p className="text-xs text-ink-muted">
            Write and edit strategy files. Saved files are picked up on the next backtest or run.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" onClick={handleValidate} disabled={validate.isPending}>
            {validate.isPending ? "Validating…" : "Validate"}
          </Button>
          <Button size="sm" onClick={handleSave} disabled={!active || save.isPending}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
          {active && active !== newName && (
            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                if (confirm(`Delete ${active}? This cannot be undone.`)) remove.mutate(active);
              }}
            >
              Delete
            </Button>
          )}
        </div>
      </div>

      {notice && (
        <div className="flex items-center gap-2 text-xs text-ink-soft">
          <Badge tone="muted">{notice}</Badge>
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-[200px_1fr] gap-3">
        <div className="min-h-0 overflow-hidden rounded border border-line bg-surface p-3">
          <FileList files={files} active={active} onSelect={(f) => { setNewName(null); setActive(f); setValidation(null); }} onNew={handleNew} />
        </div>

        <div className="flex min-h-0 flex-col gap-2">
          <div className="min-h-0 flex-1 overflow-hidden rounded border border-line">
            <Suspense fallback={<div className="p-4 text-xs text-ink-muted">Loading editor…</div>}>
              {active ? (
                <MonacoEditor
                  height="100%"
                  language="python"
                  theme={theme === "dark" ? "vs-dark" : "light"}
                  value={draft}
                  onChange={(v) => setDraft(v ?? "")}
                  options={{
                    fontSize: 13,
                    minimap: { enabled: false },
                    scrollBeyondLastLine: false,
                    tabSize: 4,
                    automaticLayout: true,
                  }}
                />
              ) : (
                <div className="grid h-full place-items-center text-xs text-ink-muted">
                  Select a file, or create a new one.
                </div>
              )}
            </Suspense>
          </div>
          <ValidationPanel result={validation} />
        </div>
      </div>
    </div>
  );
}
