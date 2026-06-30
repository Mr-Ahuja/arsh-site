import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "../../lib/api";
import { Button } from "../../components/ui/Button";

interface Props {
  open: boolean;
  onClose: () => void;
}

type Mode = "paper" | "live";

export function StartModal({ open, onClose }: Props) {
  const qc = useQueryClient();
  const overlayRef = useRef<HTMLDivElement>(null);
  const [strategy, setStrategy] = useState("");
  const [mode, setMode] = useState<Mode>("paper");
  const [paramsRaw, setParamsRaw] = useState("{}");
  const [paramsErr, setParamsErr] = useState("");

  const { data: strats } = useQuery({
    queryKey: ["strategies"],
    queryFn: () => apiGet<{ strategies: string[] }>("/engine/strategies"),
    enabled: open,
  });

  useEffect(() => {
    if (strats?.strategies.length && !strategy) {
      setStrategy(strats.strategies[0]);
    }
  }, [strats, strategy]);

  const start = useMutation({
    mutationFn: (vars: { strategy: string; mode: Mode; params: Record<string, unknown> }) =>
      apiPost("/engine/start", vars),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["engine-status"] });
      onClose();
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    let params: Record<string, unknown> = {};
    try {
      params = JSON.parse(paramsRaw);
      setParamsErr("");
    } catch {
      setParamsErr("Params must be valid JSON");
      return;
    }
    start.mutate({ strategy, mode, params });
  }

  // Close on overlay click
  function onOverlay(e: React.MouseEvent) {
    if (e.target === overlayRef.current) onClose();
  }

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onOverlay}
    >
      <div className="w-full max-w-md rounded border border-line bg-surface shadow-xl">
        <header className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold text-ink">Start Engine</h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-ink-muted hover:bg-surface-hover"
            aria-label="Close"
          >
            ✕
          </button>
        </header>

        <form onSubmit={handleSubmit} className="space-y-4 p-4">
          {/* Strategy */}
          <div>
            <label className="mb-1 block text-2xs font-medium uppercase tracking-wide text-ink-muted">
              Strategy
            </label>
            {strats?.strategies.length ? (
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                className="w-full rounded border border-line bg-surface-alt px-2.5 py-1.5 text-sm text-ink focus:outline-none focus:ring-1 focus:ring-brand"
              >
                {strats.strategies.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            ) : (
              <div className="text-xs text-ink-muted">No strategies found in strategies/</div>
            )}
          </div>

          {/* Mode */}
          <div>
            <label className="mb-1 block text-2xs font-medium uppercase tracking-wide text-ink-muted">
              Mode
            </label>
            <div className="flex gap-2">
              {(["paper", "live"] as Mode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={`flex-1 rounded border py-1.5 text-xs font-medium transition-colors ${
                    mode === m
                      ? m === "live"
                        ? "border-sell bg-neg-bg text-neg"
                        : "border-brand bg-brand-bg text-brand"
                      : "border-line text-ink-muted hover:bg-surface-hover"
                  }`}
                >
                  {m === "live" ? "⚡ Live" : "◎ Paper"}
                </button>
              ))}
            </div>
            {mode === "live" && (
              <p className="mt-1 text-2xs text-neg">
                Live mode places real orders. Confirm Kite is connected and strategy is validated in
                paper first.
              </p>
            )}
          </div>

          {/* Param overrides */}
          <div>
            <label className="mb-1 block text-2xs font-medium uppercase tracking-wide text-ink-muted">
              Param overrides (JSON)
            </label>
            <textarea
              value={paramsRaw}
              onChange={(e) => setParamsRaw(e.target.value)}
              rows={3}
              className={`w-full rounded border px-2.5 py-1.5 font-mono text-xs text-ink focus:outline-none focus:ring-1 focus:ring-brand ${
                paramsErr ? "border-neg bg-neg-bg" : "border-line bg-surface-alt"
              }`}
              placeholder='{"qty": 5}'
            />
            {paramsErr && <p className="mt-1 text-2xs text-neg">{paramsErr}</p>}
          </div>

          {start.error && (
            <p className="rounded border border-neg-bg bg-neg-bg px-3 py-2 text-xs text-neg">
              {(start.error as { message?: string })?.message ?? "Failed to start engine"}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              variant={mode === "live" ? "danger" : "primary"}
              disabled={start.isPending || !strategy}
            >
              {start.isPending ? "Starting…" : mode === "live" ? "Start Live" : "Start Paper"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
