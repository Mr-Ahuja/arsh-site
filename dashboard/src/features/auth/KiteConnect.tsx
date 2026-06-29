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
    <div className="mx-auto max-w-xl space-y-4">
      <h1 className="text-base font-semibold text-ink">Kite connection</h1>

      <Card>
        {justConnected && (
          <div className="mb-3">
            <Badge tone="pos" dot>
              Connected successfully
            </Badge>
          </div>
        )}

        {isLoading ? (
          <p className="text-xs text-ink-muted">Checking status…</p>
        ) : status?.connected ? (
          <div className="space-y-1.5">
            <Badge tone="pos" dot>
              Connected as {status.user_id}
            </Badge>
            <p className="num text-xs text-ink-muted">Token valid for {status.valid_for_date}</p>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-ink-muted">
              Log in each trading morning to mint the day&apos;s access token. It expires overnight.
            </p>
            <Button onClick={loginToKite}>Login to Kite</Button>
            <p className="text-2xs text-ink-muted">
              Credentials not set?{" "}
              <Link to="/settings" className="text-brand">
                Configure them in Settings
              </Link>
              .
            </p>
          </div>
        )}
        {error && <p className="mt-3 text-xs text-neg">{error}</p>}
      </Card>
    </div>
  );
}
