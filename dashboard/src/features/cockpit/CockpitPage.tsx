import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "../../lib/api";
import { StatTile } from "../../components/ui/StatTile";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { useEngineStore, type EngineStatus } from "../../stores/engineStore";
import { StartModal } from "./StartModal";
import { PositionCard } from "./PositionCard";
import { ActivityFeed } from "./ActivityFeed";

// ── Types ─────────────────────────────────────────────────────────────────────

interface KiteStatus {
  connected: boolean;
  user_id: string | null;
  valid_for_date: string | null;
}

// ── Kill switch dialog ────────────────────────────────────────────────────────

function KillDialog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [token, setToken] = useState("");
  const overlayRef = useRef<HTMLDivElement>(null);

  const kill = useMutation({
    mutationFn: () =>
      fetch("/api/engine/kill", {
        method: "POST",
        headers: {
          "X-Kill-Token": token,
          "X-CSRF-Token": document.cookie.match(/csrf=([^;]*)/)?.[1] ?? "",
        },
        credentials: "include",
      }).then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).detail ?? "Kill failed");
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["engine-status"] });
      onClose();
    },
  });

  function handleKill() {
    if (!token.trim()) return;
    kill.mutate();
  }

  function onOverlay(e: React.MouseEvent) {
    if (e.target === overlayRef.current) onClose();
  }

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onOverlay}
    >
      <div className="w-full max-w-sm rounded border border-neg bg-surface shadow-xl">
        <div className="border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold text-neg">Kill Switch</h2>
        </div>
        <div className="space-y-3 p-4">
          <p className="text-xs text-ink-soft">
            This immediately squares off any open position and halts the engine. Enter the kill
            token to confirm.
          </p>
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Kill token"
            autoFocus
            className="w-full rounded border border-line bg-surface-alt px-2.5 py-1.5 text-sm text-ink focus:outline-none focus:ring-1 focus:ring-neg"
            onKeyDown={(e) => e.key === "Enter" && handleKill()}
          />
          {kill.error && (
            <p className="text-xs text-neg">
              {(kill.error as { message?: string })?.message ?? "Kill failed"}
            </p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              disabled={!token.trim() || kill.isPending}
              onClick={handleKill}
            >
              {kill.isPending ? "Killing…" : "Kill now"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── SAFE-mode banner ─────────────────────────────────────────────────────────

function SafeBanner({ reason }: { reason: string | null }) {
  const qc = useQueryClient();
  const [adoptOpen, setAdoptOpen] = useState(false);

  const squareoff = useMutation({
    mutationFn: () => apiPost("/engine/reconcile/square-off"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["engine-status"] }),
  });

  const resume = useMutation({
    mutationFn: () => apiPost("/engine/resume"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["engine-status"] }),
  });

  return (
    <div className="rounded border border-neg bg-neg-bg px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex-1">
          <div className="text-xs font-semibold text-neg">SAFE MODE — Engine halted</div>
          <div className="mt-0.5 text-xs text-ink-soft">
            {reason ?? "Position mismatch between engine and broker. Resolve before trading resumes."}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => setAdoptOpen(true)}>
            Adopt position
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={squareoff.isPending}
            onClick={() => squareoff.mutate()}
          >
            Square off now
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={resume.isPending}
            onClick={() => resume.mutate()}
          >
            Resume
          </Button>
        </div>
      </div>

      {adoptOpen && (
        <AdoptForm onClose={() => setAdoptOpen(false)} onSuccess={() => {
          setAdoptOpen(false);
          qc.invalidateQueries({ queryKey: ["engine-status"] });
        }} />
      )}
    </div>
  );
}

function AdoptForm({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [side, setSide] = useState("BUY");
  const [qty, setQty] = useState(1);
  const [avgPrice, setAvgPrice] = useState(0);

  const adopt = useMutation({
    mutationFn: () => apiPost("/engine/reconcile/adopt", { side, qty, avg_price: avgPrice }),
    onSuccess,
  });

  return (
    <div className="mt-3 rounded border border-line bg-surface p-3">
      <p className="mb-2 text-2xs text-ink-muted">
        Enter the broker position to adopt. pos.vars will start fresh.
      </p>
      <div className="flex items-end gap-2">
        <div>
          <label className="block text-2xs text-ink-muted">Side</label>
          <select
            value={side}
            onChange={(e) => setSide(e.target.value)}
            className="rounded border border-line bg-surface-alt px-2 py-1 text-xs text-ink"
          >
            <option value="BUY">BUY (Long)</option>
            <option value="SELL">SELL (Short)</option>
          </select>
        </div>
        <div>
          <label className="block text-2xs text-ink-muted">Qty</label>
          <input
            type="number"
            min={1}
            value={qty}
            onChange={(e) => setQty(Number(e.target.value))}
            className="w-20 rounded border border-line bg-surface-alt px-2 py-1 text-xs text-ink"
          />
        </div>
        <div>
          <label className="block text-2xs text-ink-muted">Avg price</label>
          <input
            type="number"
            step={0.05}
            value={avgPrice}
            onChange={(e) => setAvgPrice(Number(e.target.value))}
            className="w-24 rounded border border-line bg-surface-alt px-2 py-1 text-xs text-ink"
          />
        </div>
        <Button size="sm" disabled={adopt.isPending} onClick={() => adopt.mutate()}>
          Adopt
        </Button>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

// ── Engine control bar ────────────────────────────────────────────────────────

function EngineBar({
  status,
  onStart,
  onKill,
}: {
  status: EngineStatus;
  onStart: () => void;
  onKill: () => void;
}) {
  const qc = useQueryClient();
  const { wsConnected } = useEngineStore();

  const stop = useMutation({
    mutationFn: () => apiPost("/engine/stop"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["engine-status"] }),
  });

  if (!status.running) {
    return (
      <div className="flex items-center justify-between rounded border border-line bg-surface px-4 py-2.5">
        <div className="flex items-center gap-3">
          <Badge tone="muted" dot>
            Engine idle
          </Badge>
          {wsConnected ? (
            <span className="text-2xs text-pos">● WS connected</span>
          ) : (
            <span className="text-2xs text-ink-muted">● WS reconnecting…</span>
          )}
        </div>
        <Button size="sm" onClick={onStart}>
          Start Engine
        </Button>
      </div>
    );
  }

  const modeTone = status.mode === "live" ? "neg" : "brand";
  const stratName = status.strategy?.split(".").pop() ?? status.strategy ?? "—";

  return (
    <div className="flex items-center justify-between rounded border border-line bg-surface px-4 py-2.5">
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone={modeTone} dot>
          {status.mode === "live" ? "Live" : "Paper"}
        </Badge>
        <span className="text-xs font-medium text-ink">{stratName}</span>
        <span className="text-2xs text-ink-muted">run #{status.run_id}</span>
        {wsConnected && <span className="text-2xs text-pos">● live</span>}
      </div>
      <div className="flex gap-2">
        <Button variant="ghost" size="sm" disabled={stop.isPending} onClick={() => stop.mutate()}>
          {stop.isPending ? "Stopping…" : "Stop"}
        </Button>
        <Button variant="danger" size="sm" onClick={onKill}>
          ⚡ Kill
        </Button>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function CockpitPage() {
  const { status: wsStatus, setStatus, position } = useEngineStore();
  const [startOpen, setStartOpen] = useState(false);
  const [killOpen, setKillOpen] = useState(false);

  // Poll engine status (WS updates immediately; poll reconciles after restarts)
  const { data: apiStatus } = useQuery<EngineStatus>({
    queryKey: ["engine-status"],
    queryFn: () => apiGet<EngineStatus>("/engine/status"),
    refetchInterval: 10_000,
  });

  useEffect(() => {
    if (apiStatus) setStatus(apiStatus);
  }, [apiStatus, setStatus]);

  const status = apiStatus ?? wsStatus;

  const { data: kite } = useQuery<KiteStatus>({
    queryKey: ["kite-status"],
    queryFn: () => apiGet<KiteStatus>("/kite/status"),
    refetchInterval: 60_000,
  });

  // Derived numbers
  const dayPnl = position.pnl; // realised + unrealised — runner publishes combined
  const pnlTone = dayPnl > 0 ? "pos" : dayPnl < 0 ? "neg" : "default";

  function fmtPnl(v: number) {
    const sign = v > 0 ? "+" : "";
    return `${sign}₹${Math.abs(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-3">
      {/* SAFE-mode banner */}
      {status.safe_mode && <SafeBanner reason={status.safe_mode_reason} />}

      {/* Engine control bar */}
      <EngineBar
        status={status}
        onStart={() => setStartOpen(true)}
        onKill={() => setKillOpen(true)}
      />

      {/* Stat strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile
          label="Day P&L"
          value={status.running ? fmtPnl(dayPnl) : "—"}
          sub="realized + open"
          tone={status.running ? pnlTone : "default"}
        />
        <StatTile
          label="Unrealized"
          value={status.running && position.in_position ? fmtPnl(position.pnl) : "—"}
          tone={status.running && position.in_position ? pnlTone : "default"}
        />
        <StatTile
          label="LTP"
          value={status.running && position.ltp > 0 ? `₹${position.ltp.toFixed(2)}` : "—"}
        />
        <StatTile
          label="In position"
          value={status.running ? (position.in_position ? "Yes" : "No") : "—"}
          tone={position.in_position ? "default" : "default"}
        />
        <StatTile
          label="Mode"
          value={status.running ? (status.mode ?? "—") : "—"}
        />
        <StatTile
          label="Strategy"
          value={status.running ? (status.strategy?.split(".").pop() ?? "—") : "—"}
        />
      </div>

      {/* Kite connect prompt */}
      {!kite?.connected && (
        <Card>
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-sm font-medium text-ink">Connect Zerodha Kite to begin</div>
              <p className="mt-0.5 text-xs text-ink-muted">
                The day's access token is required for market data and order execution.
              </p>
            </div>
            <Link to="/connect">
              <Button size="sm">Login to Kite</Button>
            </Link>
          </div>
        </Card>
      )}

      {/* Main grid */}
      <div className="grid gap-3 lg:grid-cols-2">
        <PositionCard runId={status.run_id} />
        <ActivityFeed />
      </div>

      {/* Modals */}
      <StartModal open={startOpen} onClose={() => setStartOpen(false)} />
      {killOpen && <KillDialog onClose={() => setKillOpen(false)} />}
    </div>
  );
}
