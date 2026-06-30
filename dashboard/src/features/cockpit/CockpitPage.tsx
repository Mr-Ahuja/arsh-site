import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiGet } from "../../lib/api";
import { StatTile } from "../../components/ui/StatTile";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";

interface KiteStatus {
  connected: boolean;
  user_id: string | null;
  valid_for_date: string | null;
}

export function CockpitPage() {
  const { data: kite } = useQuery({
    queryKey: ["kite-status"],
    queryFn: () => apiGet<KiteStatus>("/kite/status"),
  });

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-ink">Dashboard</h1>
          <p className="text-xs text-ink-muted">Live cockpit · paper / live engine</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone="muted" dot>
            Engine: idle
          </Badge>
          {/* Primary risk action. The only manual control by design — no order entry. */}
          <Button variant="danger" size="sm" disabled title="Active once the engine is running">
            Kill switch
          </Button>
        </div>
      </div>

      {/* Stat strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile label="Day P&L" value="—" sub="realized + unrealized" />
        <StatTile label="Realized" value="—" />
        <StatTile label="Unrealized" value="—" />
        <StatTile label="Open positions" value="0" />
        <StatTile label="Trades today" value="0" />
        <StatTile label="Exposure" value="—" />
      </div>

      {/* Kite connection prompt / state */}
      {!kite?.connected && (
        <Card>
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-sm font-medium text-ink">Connect Zerodha Kite to begin</div>
              <p className="mt-0.5 text-xs text-ink-muted">
                The day&apos;s access token is required for market data and execution. It expires
                overnight, so this is a daily step.
              </p>
            </div>
            <Link to="/connect">
              <Button size="sm">Login to Kite</Button>
            </Link>
          </div>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Open positions">
          <div className="py-10 text-center text-xs text-ink-muted">
            No open positions. Live positions stream here once the engine runs (Task 09).
          </div>
        </Card>
        <Card title="Recent activity">
          <div className="py-10 text-center text-xs text-ink-muted">
            Order &amp; event feed appears here (Task 08).
          </div>
        </Card>
      </div>
    </div>
  );
}
