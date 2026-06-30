import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface EquityPoint {
  date: string;
  pnl: number;
  trade_pnl: number;
  symbol: string;
}

export interface DailyPoint {
  date: string;
  pnl: number;
}

function fmtPnl(v: number) {
  const sign = v >= 0 ? "+" : "";
  return `${sign}₹${Math.abs(v).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
}

// ── Equity curve ──────────────────────────────────────────────────────────────

export function EquityChart({ data }: { data: EquityPoint[] }) {
  if (!data.length) {
    return (
      <div className="flex h-48 items-center justify-center text-xs text-ink-muted">
        No closed trades to chart.
      </div>
    );
  }

  const min = Math.min(0, ...data.map((d) => d.pnl));
  const max = Math.max(0, ...data.map((d) => d.pnl));
  const positive = (data[data.length - 1]?.pnl ?? 0) >= 0;
  const strokeColor = positive ? "var(--pos)" : "var(--neg)";

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="eq-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={strokeColor} stopOpacity={0.15} />
            <stop offset="95%" stopColor={strokeColor} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "var(--ink-muted)" }}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10, fill: "var(--ink-muted)" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `₹${v >= 0 ? "" : "-"}${Math.abs(v / 1000).toFixed(1)}k`}
          domain={[min * 1.1, max * 1.1]}
          width={52}
        />
        <Tooltip
          formatter={(v: unknown) => [fmtPnl(v as number), "Cumulative P&L"]}
          contentStyle={{
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: 3,
            fontSize: 11,
            color: "var(--ink)",
          }}
        />
        <ReferenceLine y={0} stroke="var(--line-strong)" strokeDasharray="4 2" />
        <Area
          type="monotone"
          dataKey="pnl"
          stroke={strokeColor}
          strokeWidth={1.5}
          fill="url(#eq-fill)"
          dot={false}
          activeDot={{ r: 3, fill: strokeColor }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Daily P&L bar chart ───────────────────────────────────────────────────────

export function DailyChart({ data }: { data: DailyPoint[] }) {
  if (!data.length) {
    return (
      <div className="flex h-40 items-center justify-center text-xs text-ink-muted">
        No daily data.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "var(--ink-muted)" }}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10, fill: "var(--ink-muted)" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `₹${v >= 0 ? "" : "-"}${Math.abs(v / 1000).toFixed(1)}k`}
          width={52}
        />
        <Tooltip
          formatter={(v: unknown) => [fmtPnl(v as number), "Day P&L"]}
          contentStyle={{
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: 3,
            fontSize: 11,
            color: "var(--ink)",
          }}
        />
        <ReferenceLine y={0} stroke="var(--line-strong)" />
        <Bar
          dataKey="pnl"
          radius={[2, 2, 0, 0]}
          fill="var(--brand)"
          // Color each bar based on sign
          isAnimationActive={false}
          // recharts Cell approach for per-bar color
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
