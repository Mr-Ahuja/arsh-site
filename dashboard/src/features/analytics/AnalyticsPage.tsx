import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../../lib/api";
import { Card } from "../../components/ui/Card";
import { MetricsGrid, type Metrics } from "./MetricsGrid";
import { EquityChart, DailyChart, type EquityPoint, type DailyPoint } from "./Charts";

interface Run {
  id: number;
  mode: string;
  strategy: string;
  started_at: string;
  stopped_at: string | null;
  status: string;
}

const SELECT_CLS =
  "rounded border border-line bg-surface px-2.5 py-1.5 text-xs text-ink focus:outline-none focus:ring-1 focus:ring-brand";

export function AnalyticsPage() {
  const [runId, setRunId] = useState<string>("");
  const [mode, setMode] = useState<string>("");

  const qs = [runId && `run_id=${runId}`, mode && `mode=${mode}`]
    .filter(Boolean).join("&");

  const { data: runs } = useQuery<Run[]>({
    queryKey: ["analytics-runs"],
    queryFn: () => apiGet<Run[]>("/analytics/runs"),
  });

  const { data: metrics } = useQuery<Metrics>({
    queryKey: ["analytics-metrics", qs],
    queryFn: () => apiGet<Metrics>(`/analytics/metrics?${qs}`),
  });

  const { data: equity } = useQuery<EquityPoint[]>({
    queryKey: ["analytics-equity", qs],
    queryFn: () => apiGet<EquityPoint[]>(`/analytics/equity?${qs}`),
  });

  const { data: daily } = useQuery<DailyPoint[]>({
    queryKey: ["analytics-daily", qs],
    queryFn: () => apiGet<DailyPoint[]>(`/analytics/daily?${qs}`),
  });

  return (
    <div className="mx-auto max-w-6xl space-y-3">
      {/* Header + filter strip */}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-base font-semibold text-ink">Analytics</h1>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <select
            value={mode}
            onChange={(e) => { setMode(e.target.value); setRunId(""); }}
            className={SELECT_CLS}
          >
            <option value="">All modes</option>
            <option value="paper">Paper</option>
            <option value="live">Live</option>
            <option value="backtest">Backtest</option>
          </select>

          <select
            value={runId}
            onChange={(e) => { setRunId(e.target.value); setMode(""); }}
            className={SELECT_CLS}
          >
            <option value="">All runs</option>
            {runs?.map((r) => (
              <option key={r.id} value={String(r.id)}>
                #{r.id} {r.strategy} ({r.mode}) · {r.started_at}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Metrics */}
      {metrics && metrics.total_trades > 0 ? (
        <MetricsGrid m={metrics} />
      ) : (
        <Card>
          <div className="flex h-20 items-center justify-center text-xs text-ink-muted">
            {metrics ? "No closed trades match the current filter." : "Loading…"}
          </div>
        </Card>
      )}

      {/* Equity curve */}
      <Card title="Equity Curve">
        <EquityChart data={equity ?? []} />
      </Card>

      {/* Daily P&L */}
      <Card title="Daily P&L">
        <DailyChart data={daily ?? []} />
      </Card>
    </div>
  );
}
