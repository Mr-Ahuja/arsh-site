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

function CopyRow({ label, value }: { label: string; value?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div>
      <div className="text-2xs uppercase tracking-wide text-ink-muted">{label}</div>
      <div className="mt-1 flex items-center gap-2">
        <code className="flex-1 truncate rounded border border-line bg-surface-alt px-2 py-1.5 text-xs text-ink">
          {value ?? "—"}
        </code>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            if (value) {
              navigator.clipboard.writeText(value);
              setCopied(true);
              setTimeout(() => setCopied(false), 1200);
            }
          }}
        >
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
    </div>
  );
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
      await apiPut("/settings", { api_key: apiKey, api_secret: apiSecret || undefined });
      setApiSecret("");
      setStatus("Saved.");
      await qc.invalidateQueries({ queryKey: ["settings"] });
    } catch (err) {
      setError((err as ApiError).message ?? "Save failed");
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) return <p className="text-xs text-ink-muted">Loading…</p>;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-base font-semibold text-ink">Settings</h1>

      <Card title="Zerodha API credentials">
        <p className="mb-4 text-xs text-ink-muted">
          Stored encrypted in the database. The API secret is write-only — it is never returned to
          the browser.
        </p>
        <form onSubmit={onSubmit} className="space-y-3.5">
          <Input
            label="API key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="kite api_key"
            required
          />
          <div>
            <Input
              label="API secret"
              type="password"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              placeholder={data?.kite_api_secret_set ? "•••••• (leave blank to keep)" : "kite api_secret"}
            />
            {data?.kite_api_secret_set && (
              <div className="mt-1.5">
                <Badge tone="pos" dot>
                  Secret is set
                </Badge>
              </div>
            )}
          </div>
          <div className="flex items-center gap-3 pt-1">
            <Button type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save"}
            </Button>
            {status && <span className="text-xs text-pos">{status}</span>}
            {error && <span className="text-xs text-neg">{error}</span>}
          </div>
        </form>
      </Card>

      <Card title="Kite developer console URLs">
        <p className="mb-3 text-xs text-ink-muted">
          Paste these into your app at developers.kite.trade — they must match character-for-character.
        </p>
        <div className="space-y-3">
          <CopyRow label="Redirect URL" value={data?.redirect_url} />
          <CopyRow label="Postback URL" value={data?.postback_url} />
        </div>
      </Card>
    </div>
  );
}
