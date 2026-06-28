import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiGet, type ApiError } from "../../lib/api";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";

interface KiteStatus {
  connected: boolean;
  user_id: string | null;
  valid_for_date: string | null;
}

export function KiteConnect() {
  const [params] = useSearchParams();
  const justConnected = params.get("kite") === "connected";
  const [error, setError] = useState<string | null>(null);

  const { data: status, isLoading } = useQuery({
    queryKey: ["kite-status"],
    queryFn: () => apiGet<KiteStatus>("/kite/status"),
  });

  async function loginToKite() {
    setError(null);
    try {
      const { url } = await apiGet<{ url: string }>("/kite/login-url");
      window.location.href = url;
    } catch (err) {
      setError((err as ApiError).message ?? "Could not start Kite login");
    }
  }

  return (
    <div className="max-w-xl">
      <Card>
        <h1 className="mb-1 text-lg font-semibold">Connect Zerodha Kite</h1>
        <p className="mb-4 text-sm text-ink-muted">
          Log in each trading morning to mint the day's access token.
        </p>

        {justConnected && (
          <p className="mb-3">
            <Badge tone="green">Kite connected ✓</Badge>
          </p>
        )}

        {isLoading ? (
          <p className="text-ink-muted">Checking status…</p>
        ) : status?.connected ? (
          <div className="space-y-2">
            <Badge tone="green">Connected as {status.user_id}</Badge>
            <p className="text-sm text-ink-muted">Valid for {status.valid_for_date}</p>
          </div>
        ) : (
          <div className="space-y-3">
            <Button onClick={loginToKite}>Login to Kite</Button>
            <p className="text-sm text-ink-muted">
              Credentials not set?{" "}
              <Link to="/settings" className="text-kite-blue">
                Configure them in Settings
              </Link>
              .
            </p>
          </div>
        )}
        {error && <p className="mt-3 text-sm text-kite-red">{error}</p>}
      </Card>
    </div>
  );
}
