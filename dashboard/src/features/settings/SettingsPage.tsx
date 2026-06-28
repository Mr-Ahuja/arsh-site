import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPut, type ApiError } from "../../lib/api";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";

interface SettingsData {
  kite_api_key: string;
  kite_api_secret_set: boolean;
  redirect_url: string;
  postback_url: string;
}

export function SettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiGet<SettingsData>("/settings"),
  });

  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (data) setApiKey(data.kite_api_key);
  }, [data]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setStatus(null);
    setError(null);
    setBusy(true);
    try {
      await apiPut("/settings", {
        api_key: apiKey,
        api_secret: apiSecret || undefined,
      });
      setApiSecret("");
      setStatus("Saved.");
      await qc.invalidateQueries({ queryKey: ["settings"] });
    } catch (err) {
      setError((err as ApiError).message ?? "Save failed");
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) return <p className="text-ink-muted">Loading…</p>;

  return (
    <div className="max-w-xl space-y-6">
      <Card>
        <h1 className="mb-1 text-lg font-semibold">Zerodha API credentials</h1>
        <p className="mb-4 text-sm text-ink-muted">
          Stored encrypted in the database. The secret is write-only and never returned.
        </p>
        <form onSubmit={onSubmit} className="space-y-4">
          <Input
            label="API key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="your kite api_key"
            required
          />
          <div>
            <Input
              label="API secret"
              type="password"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              placeholder={data?.kite_api_secret_set ? "•••••• (leave blank to keep)" : "your kite api_secret"}
            />
            {data?.kite_api_secret_set && (
              <p className="mt-1 text-xs">
                <Badge tone="green">secret is set ✓</Badge>
              </p>
            )}
          </div>
          {status && <p className="text-sm text-kite-green">{status}</p>}
          {error && <p className="text-sm text-kite-red">{error}</p>}
          <Button type="submit" disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </Button>
        </form>
      </Card>

      <Card>
        <h2 className="mb-2 text-sm font-semibold">Kite developer console URLs</h2>
        <p className="mb-3 text-sm text-ink-muted">
          Paste these into your app at developers.kite.trade — they must match character-for-character.
        </p>
        <dl className="space-y-2 text-sm">
          <div>
            <dt className="text-ink-muted">Redirect URL</dt>
            <dd className="break-all font-mono">{data?.redirect_url}</dd>
          </div>
          <div>
            <dt className="text-ink-muted">Postback URL</dt>
            <dd className="break-all font-mono">{data?.postback_url}</dd>
          </div>
        </dl>
      </Card>
    </div>
  );
}
