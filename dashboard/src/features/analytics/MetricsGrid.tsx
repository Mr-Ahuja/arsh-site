interface Metrics {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  profit_factor: number | null;
  total_pnl: number;
  max_drawdown: number;
  largest_win: number | null;
  largest_loss: number | null;
}

export type { Metrics };

function Tile({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "pos" | "neg" | "default";
}) {
  const color =
    tone === "pos" ? "text-pos" : tone === "neg" ? "text-neg" : "text-ink";
  return (
    <div className="rounded border border-line bg-surface p-3">
      <div className="text-2xs uppercase tracking-wide text-ink-muted">{label}</div>
      <div className={`num mt-1 text-base font-semibold ${color}`}>{value}</div>
    </div>
  );
}

function fmt(v: number, d = 2) {
  return v.toLocaleString("en-IN", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

function fmtPnl(v: number | null) {
  if (v == null) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}₹${fmt(Math.abs(v))}`;
}

export function MetricsGrid({ m }: { m: Metrics }) {
  const pnlTone = m.total_pnl > 0 ? "pos" : m.total_pnl < 0 ? "neg" : "default";

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
      <Tile
        label="Total P&L"
        value={fmtPnl(m.total_pnl)}
        tone={pnlTone}
      />
      <Tile
        label="Win rate"
        value={m.win_rate != null ? `${m.win_rate}%` : "—"}
        tone={m.win_rate != null && m.win_rate >= 50 ? "pos" : "default"}
      />
      <Tile
        label="Avg win"
        value={fmtPnl(m.avg_win)}
        tone="pos"
      />
      <Tile
        label="Avg loss"
        value={m.avg_loss != null ? `₹${fmt(Math.abs(m.avg_loss))}` : "—"}
        tone="neg"
      />
      <Tile
        label="Profit factor"
        value={m.profit_factor != null ? `${m.profit_factor}x` : "—"}
        tone={m.profit_factor != null && m.profit_factor >= 1 ? "pos" : "neg"}
      />
      <Tile
        label="Trades"
        value={`${m.wins}W / ${m.losses}L (${m.total_trades})`}
      />
      <Tile
        label="Max drawdown"
        value={m.max_drawdown > 0 ? `₹${fmt(m.max_drawdown)}` : "—"}
        tone="neg"
      />
      <Tile
        label="Largest win"
        value={fmtPnl(m.largest_win)}
        tone="pos"
      />
      <Tile
        label="Largest loss"
        value={m.largest_loss != null ? `₹${fmt(Math.abs(m.largest_loss))}` : "—"}
        tone="neg"
      />
    </div>
  );
}
