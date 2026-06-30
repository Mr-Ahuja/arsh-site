import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../../lib/api";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { useEngineStore } from "../../stores/engineStore";

interface TradeDetail {
  id: number;
  symbol: string;
  side: string;
  qty: number;
  entry_price: number;
  entry_at: string;
  status: string;
  mode: string;
}

interface TradeVarEntry {
  key: string;
  value: unknown;
}

function fmt(v: number, decimals = 2) {
  return v.toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtPnl(v: number) {
  const sign = v >= 0 ? "+" : "";
  return `${sign}₹${fmt(Math.abs(v))}`;
}

function fmtDuration(isoStart: string) {
  const secs = Math.floor((Date.now() - new Date(isoStart).getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  const m = Math.floor(secs / 60);
  if (m < 60) return `${m}m ${secs % 60}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

export function PositionCard({ runId }: { runId: number | null }) {
  const { position } = useEngineStore();
  const [, tick] = useState(0);

  // Re-render every second to update the duration clock
  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 1_000);
    return () => clearInterval(id);
  }, []);

  const { data: trades } = useQuery<TradeDetail[]>({
    queryKey: ["open-trades", runId],
    queryFn: () => apiGet(`/engine/trades?run_id=${runId}&status=open`),
    enabled: position.in_position && runId != null,
    refetchInterval: 5_000,
  });

  const trade = trades?.[0] ?? null;

  if (!position.in_position) {
    return (
      <Card title="Position">
        <div className="flex h-28 items-center justify-center text-xs text-ink-muted">
          Flat — no open position
        </div>
      </Card>
    );
  }

  const pnlTone = position.pnl >= 0 ? "text-pos" : "text-neg";
  const pnlBg = position.pnl >= 0 ? "bg-pos-bg" : "bg-neg-bg";

  return (
    <Card title="Position">
      {/* Header row */}
      <div className="mb-3 flex items-center justify-between">
        <div>
          <span className="text-sm font-semibold text-ink">{trade?.symbol ?? "—"}</span>
          {trade && (
            <span className="ml-2">
              <Badge tone={trade.side === "BUY" ? "brand" : "neg"}>
                {trade.side === "BUY" ? "LONG" : "SHORT"}
              </Badge>
            </span>
          )}
        </div>
        {trade && (
          <span className="text-2xs text-ink-muted">{fmtDuration(trade.entry_at)} ago</span>
        )}
      </div>

      {/* P&L strip */}
      <div className={`mb-3 rounded px-3 py-2 ${pnlBg}`}>
        <div className={`num text-xl font-bold leading-tight ${pnlTone}`}>
          {fmtPnl(position.pnl)}
        </div>
        {trade && (
          <div className="mt-0.5 text-2xs text-ink-muted">
            Entry ₹{fmt(trade.entry_price)} · LTP ₹{fmt(position.ltp)} · Qty {trade.qty}
          </div>
        )}
      </div>

      {/* Metrics grid */}
      <div className="mb-3 grid grid-cols-3 gap-2 text-center">
        <div className="rounded border border-line p-2">
          <div className="text-2xs text-ink-muted">LTP</div>
          <div className="num text-sm font-semibold text-ink">{fmt(position.ltp)}</div>
        </div>
        <div className="rounded border border-line p-2">
          <div className="text-2xs text-ink-muted">Entry</div>
          <div className="num text-sm font-semibold text-ink">{fmt(trade?.entry_price ?? 0)}</div>
        </div>
        <div className="rounded border border-line p-2">
          <div className="text-2xs text-ink-muted">Qty</div>
          <div className="num text-sm font-semibold text-ink">{trade?.qty ?? 0}</div>
        </div>
      </div>

      {/* pos.vars table — rendered from activity stream / polling */}
      <VarsTable runId={runId} tradeId={trade?.id ?? null} />
    </Card>
  );
}

function VarsTable({ runId, tradeId }: { runId: number | null; tradeId: number | null }) {
  const { data: vars } = useQuery<TradeVarEntry[]>({
    queryKey: ["trade-vars", tradeId],
    queryFn: () => apiGet(`/engine/trades/${tradeId}/vars`),
    enabled: tradeId != null && runId != null,
    refetchInterval: 2_000,
  });

  if (!vars?.length) return null;

  return (
    <div>
      <div className="mb-1 text-2xs font-medium uppercase tracking-wide text-ink-muted">
        pos.vars
      </div>
      <table className="w-full text-xs">
        <tbody>
          {vars.map((v) => (
            <tr key={v.key} className="border-t border-line">
              <td className="py-0.5 pr-3 font-medium text-ink-soft">{v.key}</td>
              <td className="num py-0.5 text-right text-ink">
                {typeof v.value === "number" ? v.value.toFixed(2) : String(v.value)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
