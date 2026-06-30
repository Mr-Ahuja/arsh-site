import { useState } from "react";

// Index reference rows. Values are placeholders (—) until the live tick feed lands
// (Task 03). This conveys Kite's dense, glanceable watchlist layout honestly.
const INDICES = ["NIFTY 50", "NIFTY BANK", "NIFTY FIN SERVICE", "SENSEX"];

function WatchRow({ symbol }: { symbol: string }) {
  return (
    <div className="group flex items-center justify-between border-b border-line/60 px-3 py-1.5 text-xs hover:bg-surface-hover">
      <span className="font-medium text-ink-soft">{symbol}</span>
      <div className="flex items-center gap-3">
        {/* Contextual action appears on hover (chart). No order entry — this is a
            monitoring cockpit, not a manual trading screen. */}
        <button
          className="hidden rounded px-1.5 py-0.5 text-2xs text-brand hover:bg-brand-bg group-hover:block"
          title="Chart (coming in a later task)"
          disabled
        >
          Chart
        </button>
        <span className="num w-16 text-right text-ink-muted">—</span>
        <span className="num w-12 text-right text-ink-muted">—</span>
      </div>
    </div>
  );
}

export function Watchlist() {
  const [q, setQ] = useState("");
  const rows = INDICES.filter((s) => s.toLowerCase().includes(q.toLowerCase()));

  return (
    <aside className="flex w-[260px] shrink-0 flex-col border-r border-line bg-surface">
      <div className="border-b border-line p-2">
        <div className="relative">
          <svg
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search eg: infy, nifty fut"
            className="h-8 w-full rounded border border-line bg-surface-alt pl-8 pr-2 text-xs text-ink placeholder:text-ink-muted outline-none focus:border-brand"
          />
        </div>
      </div>

      <div className="flex items-center justify-between px-3 py-1.5">
        <span className="text-2xs uppercase tracking-wide text-ink-muted">Indices</span>
        <span className="text-2xs text-ink-muted">{rows.length}</span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {rows.map((s) => (
          <WatchRow key={s} symbol={s} />
        ))}
      </div>

      <div className="border-t border-line px-3 py-2 text-2xs leading-relaxed text-ink-muted">
        Live quotes &amp; instrument search arrive with the market-data layer (Task 03).
      </div>
    </aside>
  );
}
