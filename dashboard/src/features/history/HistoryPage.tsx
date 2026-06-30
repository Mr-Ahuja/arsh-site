import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../../lib/api";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";

// ── Types ─────────────────────────────────────────────────────────────────────

interface TradeRow {
  id: number;
  run_id: number | null;
  symbol: string;
  side: string;
  qty: number;
  mode: string;
  strategy: string | null;
  entry_price: number;
  entry_at: string;
  exit_price: number | null;
  exit_at: string | null;
  pnl: number | null;
  status: string;
  exit_reason: string | null;
  duration_s: number | null;
}

interface Summary {
  total: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  total_pnl: number | null;
}

interface HistoryResponse {
  trades: TradeRow[];
  total: number;
  page: number;
  pages: number;
  limit: number;
  summary: Summary;
}

interface Filters {
  mode: string;
  status: string;
  exit_reason: string;
  date_from: string;
  date_to: string;
  symbol: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(v: number, d = 2) {
  return v.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
}

function fmtPnl(v: number) {
  const sign = v >= 0 ? "+" : "";
  return `${sign}₹${fmt(Math.abs(v))}`;
}

function fmtDuration(secs: number) {
  if (secs < 60) return `${secs}s`;
  const m = Math.floor(secs / 60);
  if (m < 60) return `${m}m ${secs % 60}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

function fmtDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "2-digit", month: "short",
    hour: "2-digit", minute: "2-digit", hour12: false,
  });
}

function exitReasonLabel(r: string | null) {
  if (!r) return "—";
  return {
    strategy: "Strategy",
    forced_squareoff: "Force exit",
    daily_loss: "Daily loss",
    kill_switch: "Kill switch",
    error: "Error",
    manual: "Manual",
  }[r] ?? r;
}

function exitReasonTone(r: string | null): "neg" | "warn" | "brand" | "muted" {
  if (!r) return "muted";
  if (r === "kill_switch" || r === "error") return "neg";
  if (r === "daily_loss" || r === "forced_squareoff") return "warn";
  if (r === "strategy") return "brand";
  return "muted";
}

// ── Filter bar ────────────────────────────────────────────────────────────────

const SELECT_CLS =
  "rounded border border-line bg-surface px-2 py-1 text-xs text-ink focus:outline-none focus:ring-1 focus:ring-brand";
const INPUT_CLS =
  "rounded border border-line bg-surface px-2 py-1 text-xs text-ink placeholder:text-ink-muted focus:outline-none focus:ring-1 focus:ring-brand";

function FilterBar({
  filters,
  onChange,
  onExport,
}: {
  filters: Filters;
  onChange: (f: Partial<Filters>) => void;
  onExport: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="date"
        value={filters.date_from}
        onChange={(e) => onChange({ date_from: e.target.value })}
        className={INPUT_CLS}
      />
      <span className="text-xs text-ink-muted">to</span>
      <input
        type="date"
        value={filters.date_to}
        onChange={(e) => onChange({ date_to: e.target.value })}
        className={INPUT_CLS}
      />

      <select
        value={filters.mode}
        onChange={(e) => onChange({ mode: e.target.value })}
        className={SELECT_CLS}
      >
        <option value="">All modes</option>
        <option value="paper">Paper</option>
        <option value="live">Live</option>
        <option value="backtest">Backtest</option>
      </select>

      <select
        value={filters.status}
        onChange={(e) => onChange({ status: e.target.value })}
        className={SELECT_CLS}
      >
        <option value="">All statuses</option>
        <option value="closed">Closed</option>
        <option value="open">Open</option>
        <option value="cancelled">Cancelled</option>
      </select>

      <select
        value={filters.exit_reason}
        onChange={(e) => onChange({ exit_reason: e.target.value })}
        className={SELECT_CLS}
      >
        <option value="">All exit reasons</option>
        <option value="strategy">Strategy</option>
        <option value="forced_squareoff">Force exit</option>
        <option value="daily_loss">Daily loss</option>
        <option value="kill_switch">Kill switch</option>
        <option value="error">Error</option>
        <option value="manual">Manual</option>
      </select>

      <input
        type="text"
        value={filters.symbol}
        onChange={(e) => onChange({ symbol: e.target.value })}
        placeholder="Symbol…"
        className={`w-28 ${INPUT_CLS}`}
      />

      <div className="ml-auto">
        <Button variant="ghost" size="sm" onClick={onExport}>
          Export CSV
        </Button>
      </div>
    </div>
  );
}

// ── Summary strip ─────────────────────────────────────────────────────────────

function SummaryStrip({ s }: { s: Summary }) {
  const pnlTone = (s.total_pnl ?? 0) >= 0 ? "text-pos" : "text-neg";
  return (
    <div className="flex flex-wrap items-center gap-4 text-xs text-ink-soft">
      <span>
        <span className="font-medium text-ink">{s.total}</span> trade{s.total !== 1 ? "s" : ""}
      </span>
      {s.total > 0 && (
        <>
          <span>
            <span className="text-pos font-medium">{s.wins}W</span>
            {" / "}
            <span className="text-neg font-medium">{s.losses}L</span>
          </span>
          {s.win_rate !== null && (
            <span>
              Win rate{" "}
              <span className="font-medium text-ink">{s.win_rate}%</span>
            </span>
          )}
          {s.total_pnl !== null && (
            <span>
              Total P&L{" "}
              <span className={`num font-semibold ${pnlTone}`}>{fmtPnl(s.total_pnl)}</span>
            </span>
          )}
        </>
      )}
    </div>
  );
}

// ── Trade table ───────────────────────────────────────────────────────────────

const TH = "px-3 py-2 text-left text-2xs font-semibold uppercase tracking-wide text-ink-muted";
const TD = "px-3 py-2 text-xs";

function TradeTable({ trades }: { trades: TradeRow[] }) {
  if (!trades.length) {
    return (
      <div className="flex h-48 items-center justify-center text-xs text-ink-muted">
        No trades match the current filters.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b border-line bg-surface-alt">
            <th className={TH}>#</th>
            <th className={TH}>Date (IST)</th>
            <th className={TH}>Symbol</th>
            <th className={TH}>Side</th>
            <th className={TH}>Qty</th>
            <th className={TH}>Mode</th>
            <th className={TH}>Strategy</th>
            <th className={`${TH} text-right`}>Entry</th>
            <th className={`${TH} text-right`}>Exit</th>
            <th className={`${TH} text-right`}>P&L</th>
            <th className={TH}>Duration</th>
            <th className={TH}>Exit reason</th>
            <th className={TH}>Status</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => {
            const pnlColor =
              t.pnl == null ? "text-ink-muted" : t.pnl >= 0 ? "text-pos" : "text-neg";
            const sideTone = t.side === "BUY" ? "brand" : "neg";
            const modeTone = t.mode === "live" ? "neg" : t.mode === "backtest" ? "muted" : "brand";

            return (
              <tr key={t.id} className="border-b border-line hover:bg-surface-hover">
                <td className={`${TD} text-ink-muted`}>{t.id}</td>
                <td className={`${TD} text-ink-soft`}>
                  {t.entry_at ? fmtDate(t.entry_at) : "—"}
                </td>
                <td className={`${TD} font-medium text-ink`}>{t.symbol}</td>
                <td className={TD}>
                  <Badge tone={sideTone}>{t.side === "BUY" ? "LONG" : "SHORT"}</Badge>
                </td>
                <td className={`${TD} num text-ink-soft`}>{t.qty}</td>
                <td className={TD}>
                  <Badge tone={modeTone}>{t.mode}</Badge>
                </td>
                <td className={`${TD} text-ink-soft`}>{t.strategy ?? "—"}</td>
                <td className={`${TD} num text-right text-ink`}>₹{fmt(t.entry_price)}</td>
                <td className={`${TD} num text-right text-ink-soft`}>
                  {t.exit_price != null ? `₹${fmt(t.exit_price)}` : "—"}
                </td>
                <td className={`${TD} num text-right font-medium ${pnlColor}`}>
                  {t.pnl != null ? fmtPnl(t.pnl) : "—"}
                </td>
                <td className={`${TD} text-ink-soft`}>
                  {t.duration_s != null ? fmtDuration(t.duration_s) : "—"}
                </td>
                <td className={TD}>
                  <Badge tone={exitReasonTone(t.exit_reason)}>
                    {exitReasonLabel(t.exit_reason)}
                  </Badge>
                </td>
                <td className={TD}>
                  <Badge tone={t.status === "open" ? "pos" : "muted"}>
                    {t.status}
                  </Badge>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Pagination ────────────────────────────────────────────────────────────────

function Pagination({
  page,
  pages,
  total,
  limit,
  onPage,
}: {
  page: number;
  pages: number;
  total: number;
  limit: number;
  onPage: (p: number) => void;
}) {
  if (pages <= 1) return null;

  const start = (page - 1) * limit + 1;
  const end = Math.min(page * limit, total);

  // Show a window of pages around current
  const range: number[] = [];
  for (let p = Math.max(1, page - 2); p <= Math.min(pages, page + 2); p++) {
    range.push(p);
  }

  return (
    <div className="flex items-center justify-between text-xs text-ink-muted">
      <span>
        {start}–{end} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          disabled={page === 1}
          onClick={() => onPage(page - 1)}
          className="rounded px-2 py-1 hover:bg-surface-hover disabled:opacity-30"
        >
          ←
        </button>
        {range[0] > 1 && (
          <>
            <button onClick={() => onPage(1)} className="rounded px-2 py-1 hover:bg-surface-hover">1</button>
            {range[0] > 2 && <span className="px-1">…</span>}
          </>
        )}
        {range.map((p) => (
          <button
            key={p}
            onClick={() => onPage(p)}
            className={`rounded px-2 py-1 ${
              p === page
                ? "bg-brand text-white"
                : "hover:bg-surface-hover"
            }`}
          >
            {p}
          </button>
        ))}
        {range[range.length - 1] < pages && (
          <>
            {range[range.length - 1] < pages - 1 && <span className="px-1">…</span>}
            <button onClick={() => onPage(pages)} className="rounded px-2 py-1 hover:bg-surface-hover">{pages}</button>
          </>
        )}
        <button
          disabled={page === pages}
          onClick={() => onPage(page + 1)}
          className="rounded px-2 py-1 hover:bg-surface-hover disabled:opacity-30"
        >
          →
        </button>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

const EMPTY_FILTERS: Filters = {
  mode: "",
  status: "",
  exit_reason: "",
  date_from: "",
  date_to: "",
  symbol: "",
};

function buildQueryString(filters: Filters, page: number, limit: number, format?: string) {
  const p = new URLSearchParams();
  if (filters.mode) p.set("mode", filters.mode);
  if (filters.status) p.set("status", filters.status);
  if (filters.exit_reason) p.set("exit_reason", filters.exit_reason);
  if (filters.date_from) p.set("date_from", filters.date_from);
  if (filters.date_to) p.set("date_to", filters.date_to);
  if (filters.symbol) p.set("symbol", filters.symbol);
  if (format) p.set("format", format);
  p.set("page", String(page));
  p.set("limit", String(limit));
  return p.toString();
}

export function HistoryPage() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const limit = 50;

  function applyFilter(partial: Partial<Filters>) {
    setFilters((f) => ({ ...f, ...partial }));
    setPage(1);
  }

  const qs = buildQueryString(filters, page, limit);
  const { data, isLoading, error } = useQuery<HistoryResponse>({
    queryKey: ["history", qs],
    queryFn: () => apiGet<HistoryResponse>(`/history/trades?${qs}`),
    placeholderData: (prev) => prev,
  });

  function handleExport() {
    const exportQs = buildQueryString(filters, 1, 9999, "csv");
    window.open(`/api/history/trades?${exportQs}`, "_blank");
  }

  return (
    <div className="mx-auto max-w-7xl space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-base font-semibold text-ink">Trade History</h1>
      </div>

      <Card>
        <div className="space-y-3">
          <FilterBar filters={filters} onChange={applyFilter} onExport={handleExport} />

          {data && <SummaryStrip s={data.summary} />}
        </div>
      </Card>

      <Card>
        {isLoading && !data && (
          <div className="flex h-48 items-center justify-center text-xs text-ink-muted">
            Loading…
          </div>
        )}
        {error && (
          <div className="flex h-48 items-center justify-center text-xs text-neg">
            Failed to load trades.
          </div>
        )}
        {data && (
          <div className="space-y-3">
            <TradeTable trades={data.trades} />
            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              limit={data.limit}
              onPage={(p) => setPage(p)}
            />
          </div>
        )}
      </Card>
    </div>
  );
}
