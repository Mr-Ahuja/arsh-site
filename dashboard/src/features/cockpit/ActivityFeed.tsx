import { Card } from "../../components/ui/Card";
import { useEngineStore, type ActivityItem } from "../../stores/engineStore";

function timeAgo(ts: number) {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

interface KindMeta {
  icon: string;
  label: (p: Record<string, unknown>) => string;
  getTone: (p: Record<string, unknown>) => string;
}

const KIND_META: Record<string, KindMeta> = {
  engine_started: {
    icon: "▶",
    label: (p) => `Engine started · ${p.mode} · ${String(p.strategy ?? "").split(".").pop()}`,
    getTone: () => "text-brand",
  },
  engine_stopped: {
    icon: "■",
    label: (p) => `Engine stopped · ${p.reason ?? "manual"}`,
    getTone: () => "text-ink-muted",
  },
  kill_switch: {
    icon: "⚡",
    label: () => "Kill switch triggered",
    getTone: () => "text-neg",
  },
  trade_closed: {
    icon: "●",
    label: (p) => {
      const pnl = p.pnl as number;
      const sign = pnl >= 0 ? "+" : "";
      return `Trade closed · ${sign}₹${Math.abs(pnl).toFixed(2)} · ${p.reason}`;
    },
    getTone: (p) => ((p.pnl as number) >= 0 ? "text-pos" : "text-neg"),
  },
  order_fill: {
    icon: "◈",
    label: (p) => `Fill ${p.state} · ${p.qty}@₹${Number(p.price).toFixed(2)}`,
    getTone: () => "text-ink-soft",
  },
  position_adopted: {
    icon: "↗",
    label: (p) => `Position adopted · ${p.side} ${p.qty}`,
    getTone: () => "text-warn",
  },
  alert: {
    icon: "!",
    label: (p) => String(p.message ?? "alert"),
    getTone: () => "text-warn",
  },
};

function ActivityRow({ item }: { item: ActivityItem }) {
  const meta: KindMeta = KIND_META[item.kind] ?? {
    icon: "·",
    label: () => item.kind,
    getTone: () => "text-ink-muted",
  };
  const toneCls = meta.getTone(item.payload);

  return (
    <div className="flex items-start gap-2 border-b border-line py-2 last:border-0">
      <span className={`mt-0.5 w-4 shrink-0 text-center text-xs ${toneCls}`}>{meta.icon}</span>
      <div className="min-w-0 flex-1">
        <div className={`text-xs ${toneCls}`}>{meta.label(item.payload)}</div>
      </div>
      <div className="shrink-0 text-2xs text-ink-muted">{timeAgo(item.ts)}</div>
    </div>
  );
}

export function ActivityFeed() {
  const { activity, clearActivity } = useEngineStore();

  return (
    <Card
      title="Activity"
      actions={
        activity.length > 0 ? (
          <button
            onClick={clearActivity}
            className="text-2xs text-ink-muted hover:text-ink"
          >
            Clear
          </button>
        ) : undefined
      }
    >
      {activity.length === 0 ? (
        <div className="flex h-28 items-center justify-center text-xs text-ink-muted">
          Events stream here once the engine runs
        </div>
      ) : (
        <div className="max-h-72 overflow-y-auto">
          {activity.map((item) => (
            <ActivityRow key={item.id} item={item} />
          ))}
        </div>
      )}
    </Card>
  );
}
