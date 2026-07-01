import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "../../lib/api";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { MetricsGrid, type Metrics } from "../analytics/MetricsGrid";
import { EquityChart, type EquityPoint } from "../analytics/Charts";
import { InstrumentPicker, type Instrument } from "./InstrumentPicker";

// ── Types ─────────────────────────────────────────────────────────────────────

interface BacktestRow {
  id: number;
  strategy: string;
  strategy_full: string;
  symbol: string;
  timeframe: string;
  date_from: string;
  date_to: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  run_id?: number;
  metrics?: Metrics;
  error?: string;
  result?: { run_id?: number; metrics?: Metrics; error?: string };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const INPUT_CLS =
  "w-full rounded border border-line bg-surface-alt px-2.5 py-1.5 text-xs text-ink placeholder:text-ink-muted focus:outline-none focus:ring-1 focus:ring-brand";
const SELECT_CLS =
  "w-full rounded border border-line bg-surface-alt px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:ring-1 focus:ring-brand";
const LABEL_CLS = "mb-1 block text-2xs font-medium uppercase tracking-wide text-ink-muted";

function statusTone(s: string): "pos" | "neg" | "warn" | "muted" | "brand" {
  if (s === "done") return "pos";
  if (s === "error") return "neg";
  if (s === "running") return "brand";
  return "muted";
}

// ── Backtest form ─────────────────────────────────────────────────────────────

function BacktestForm({ onSubmitted }: { onSubmitted: (id: number) => void }) {
  const qc = useQueryClient();
  const [strategy, setStrategy] = useState("");
  const [instrument, setInstrument] = useState<Instrument | null>(null);
  const [timeframe, setTimeframe] = useState("5minute");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [paramsRaw, setParamsRaw] = useState("{}");
  const [paramsErr, setParamsErr] = useState("");

  const { data: strats } = useQuery({
    queryKey: ["strategies"],
    queryFn: () => apiGet<{ strategies: string[] }>("/engine/strategies"),
  });

  useEffect(() => {
    if (strats?.strategies.length && !strategy) {
      setStrategy(strats.strategies[0]);
    }
  }, [strats, strategy]);

  const submit = useMutation({
    mutationFn: (body: object) => apiPost<{ id: number }>("/backtest", body),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["backtests"] });
      onSubmitted(data.id);
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    let params = {};
    try {
      params = JSON.parse(paramsRaw);
      setParamsErr("");
    } catch {
      setParamsErr("Must be valid JSON");
      return;
    }
    if (!instrument) return;
    submit.mutate({
      strategy,
      symbol: String(instrument.instrument_token),
      timeframe,
      date_from: dateFrom,
      date_to: dateTo,
      params,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className={LABEL_CLS}>Strategy</label>
        <select value={strategy} onChange={(e) => setStrategy(e.target.value)} className={SELECT_CLS}>
          {strats?.strategies.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div>
        <label className={LABEL_CLS}>Instrument</label>
        <InstrumentPicker value={instrument} onChange={setInstrument} />
      </div>

      <div>
        <label className={LABEL_CLS}>Timeframe</label>
        <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className={SELECT_CLS}>
          {["minute", "3minute", "5minute", "10minute", "15minute", "30minute", "60minute", "day"].map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className={LABEL_CLS}>From</label>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className={INPUT_CLS} required />
        </div>
        <div>
          <label className={LABEL_CLS}>To</label>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className={INPUT_CLS} required />
        </div>
      </div>

      <div>
        <label className={LABEL_CLS}>Param overrides (JSON)</label>
        <textarea
          value={paramsRaw}
          onChange={(e) => setParamsRaw(e.target.value)}
          rows={2}
          className={`font-mono ${INPUT_CLS} ${paramsErr ? "border-neg" : ""}`}
          placeholder='{"qty": 10}'
        />
        {paramsErr && <p className="text-2xs text-neg">{paramsErr}</p>}
      </div>

      {submit.error && (
        <p className="rounded border border-neg bg-neg-bg px-2 py-1.5 text-xs text-neg">
          {(submit.error as { message?: string }).message ?? "Submission failed"}
        </p>
      )}

      <Button type="submit" size="sm" disabled={submit.isPending || !strategy || !instrument}>
        {submit.isPending ? "Submitting…" : "Run Backtest"}
      </Button>
    </form>
  );
}

// ── Backtest list ─────────────────────────────────────────────────────────────

function BacktestList({
  rows,
  selectedId,
  onSelect,
}: {
  rows: BacktestRow[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  if (!rows.length) {
    return <p className="text-xs text-ink-muted">No backtests yet. Run one on the left.</p>;
  }

  return (
    <div className="space-y-1.5">
      {rows.map((r) => (
        <button
          key={r.id}
          onClick={() => onSelect(r.id)}
          className={`w-full rounded border px-3 py-2 text-left transition-colors ${
            selectedId === r.id
              ? "border-brand bg-brand-bg"
              : "border-line hover:bg-surface-hover"
          }`}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-medium text-ink">
              #{r.id} {r.strategy}
            </span>
            <Badge tone={statusTone(r.status)}>{r.status}</Badge>
          </div>
          <div className="mt-0.5 text-2xs text-ink-muted">
            {r.symbol} · {r.timeframe} · {r.date_from} → {r.date_to}
          </div>
          {r.metrics && (
            <div className="mt-0.5 text-2xs font-medium">
              <span className={r.metrics.total_pnl >= 0 ? "text-pos" : "text-neg"}>
                {r.metrics.total_pnl >= 0 ? "+" : ""}₹{r.metrics.total_pnl.toLocaleString("en-IN")}
              </span>
              <span className="ml-2 text-ink-muted">
                {r.metrics.total_trades} trades · {r.metrics.win_rate ?? 0}% WR
              </span>
            </div>
          )}
          {r.error && (
            <div className="mt-0.5 text-2xs text-neg truncate">{r.error}</div>
          )}
        </button>
      ))}
    </div>
  );
}

// ── Results panel ─────────────────────────────────────────────────────────────

function ResultsPanel({ btId }: { btId: number }) {
  const { data: bt } = useQuery<BacktestRow>({
    queryKey: ["backtest", btId],
    queryFn: () => apiGet<BacktestRow>(`/backtest/${btId}`),
    refetchInterval: (q) =>
      q.state.data?.status === "running" || q.state.data?.status === "pending"
        ? 2000
        : false,
  });

  const runId = bt?.result?.run_id ?? bt?.run_id;
  const metrics: Metrics | undefined = bt?.result?.metrics ?? bt?.metrics;

  const { data: equity } = useQuery<EquityPoint[]>({
    queryKey: ["bt-equity", runId],
    queryFn: () => apiGet<EquityPoint[]>(`/analytics/equity?run_id=${runId}`),
    enabled: !!runId,
  });

  if (!bt) return <div className="text-xs text-ink-muted">Loading…</div>;

  if (bt.status === "pending" || bt.status === "running") {
    return (
      <div className="flex h-32 items-center justify-center gap-2 text-xs text-ink-muted">
        <span className="animate-spin">⟳</span>
        Backtest {bt.status}…
      </div>
    );
  }

  if (bt.status === "error") {
    return (
      <div className="rounded border border-neg bg-neg-bg px-4 py-3 text-xs text-neg">
        Backtest failed: {bt.result?.error ?? bt.error ?? "unknown error"}
      </div>
    );
  }

  if (!metrics) return <div className="text-xs text-ink-muted">No results.</div>;

  return (
    <div className="space-y-3">
      <div className="text-xs text-ink-muted">
        #{bt.id} · {bt.strategy} · {bt.symbol} · {bt.timeframe} · {bt.date_from} → {bt.date_to}
        {bt.finished_at && <span className="ml-2">· Completed {bt.finished_at}</span>}
      </div>
      <MetricsGrid m={metrics} />
      <Card title="Equity Curve">
        <EquityChart data={equity ?? []} />
      </Card>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function BacktestPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const qc = useQueryClient();

  const { data: backtests } = useQuery<BacktestRow[]>({
    queryKey: ["backtests"],
    queryFn: () => apiGet<BacktestRow[]>("/backtest"),
    refetchInterval: 5000,
  });

  function handleSubmitted(id: number) {
    setSelectedId(id);
    qc.invalidateQueries({ queryKey: ["backtests"] });
  }

  return (
    <div className="mx-auto max-w-7xl space-y-3">
      <h1 className="text-base font-semibold text-ink">Backtest Runner</h1>

      <div className="grid gap-3 lg:grid-cols-3">
        {/* Left: form + history */}
        <div className="space-y-3 lg:col-span-1">
          <Card title="New backtest">
            <BacktestForm onSubmitted={handleSubmitted} />
          </Card>
          <Card title="Past backtests">
            <BacktestList
              rows={backtests ?? []}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </Card>
        </div>

        {/* Right: results */}
        <div className="lg:col-span-2">
          {selectedId ? (
            <Card title="Results">
              <ResultsPanel btId={selectedId} />
            </Card>
          ) : (
            <Card>
              <div className="flex h-48 items-center justify-center text-xs text-ink-muted">
                Select a backtest on the left to view results, or run a new one.
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
