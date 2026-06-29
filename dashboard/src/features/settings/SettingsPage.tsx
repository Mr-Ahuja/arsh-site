import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPut, apiPost, type ApiError } from "../../lib/api";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";

interface SettingsData {
  kite_api_key: string;
  kite_api_secret_set: boolean;
  redirect_url: string;
  postback_url: string;
  telegram_bot_token_set: boolean;
  telegram_chat_id: string;
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

  // --- Kite form state ---
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [kiteStatus, setKiteStatus] = useState<string | null>(null);
  const [kiteError, setKiteError] = useState<string | null>(null);
  const [kiteBusy, setKiteBusy] = useState(false);

  // --- Telegram form state ---
  const [tgToken, setTgToken] = useState("");
  const [tgChatId, setTgChatId] = useState("");
  const [tgStatus, setTgStatus] = useState<string | null>(null);
  const [tgError, setTgError] = useState<string | null>(null);
  const [tgBusy, setTgBusy] = useState(false);
  const [tgTestBusy, setTgTestBusy] = useState(false);

  useEffect(() => {
    if (data) {
      setApiKey(data.kite_api_key);
      setTgChatId(data.telegram_chat_id);
    }
  }, [data]);

  async function onKiteSubmit(e: FormEvent) {
    e.preventDefault();
    setKiteStatus(null);
    setKiteError(null);
    setKiteBusy(true);
    try {
      await apiPut("/settings", { api_key: apiKey, api_secret: apiSecret || undefined });
      setApiSecret("");
      setKiteStatus("Saved.");
      await qc.invalidateQueries({ queryKey: ["settings"] });
    } catch (err) {
      setKiteError((err as ApiError).message ?? "Save failed");
    } finally {
      setKiteBusy(false);
    }
  }

  async function onTelegramSubmit(e: FormEvent) {
    e.preventDefault();
    setTgStatus(null);
    setTgError(null);
    setTgBusy(true);
    try {
      await apiPut("/settings/telegram", {
        bot_token: tgToken || undefined,
        chat_id: tgChatId || undefined,
      });
      setTgToken("");
      setTgStatus("Saved.");
      await qc.invalidateQueries({ queryKey: ["settings"] });
    } catch (err) {
      setTgError((err as ApiError).message ?? "Save failed");
    } finally {
      setTgBusy(false);
    }
  }

  async function onTelegramTest() {
    setTgStatus(null);
    setTgError(null);
    setTgTestBusy(true);
    try {
      await apiPost("/settings/telegram/test", {});
      setTgStatus("Test message sent — check your Telegram.");
    } catch (err) {
      setTgError((err as ApiError).message ?? "Test failed");
    } finally {
      setTgTestBusy(false);
    }
  }

  const tgFullyConfigured = data?.telegram_bot_token_set && !!data?.telegram_chat_id;

  if (isLoading) return <p className="text-xs text-ink-muted">Loading…</p>;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-base font-semibold text-ink">Settings</h1>

      <Card title="Zerodha API credentials">
        <p className="mb-4 text-xs text-ink-muted">
          Stored encrypted in the database. The API secret is write-only — it is never returned to
          the browser.
        </p>
        <form onSubmit={onKiteSubmit} className="space-y-3.5">
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
                <Badge tone="pos" dot>Secret is set</Badge>
              </div>
            )}
          </div>
          <div className="flex items-center gap-3 pt-1">
            <Button type="submit" disabled={kiteBusy}>
              {kiteBusy ? "Saving…" : "Save"}
            </Button>
            {kiteStatus && <span className="text-xs text-pos">{kiteStatus}</span>}
            {kiteError && <span className="text-xs text-neg">{kiteError}</span>}
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

      <Card title="Telegram alerts">
        <p className="mb-4 text-xs text-ink-muted">
          The engine sends trade and risk alerts via a Telegram bot. The bot token is write-only and
          stored encrypted — it is never returned to the browser.
        </p>
        <form onSubmit={onTelegramSubmit} className="space-y-3.5">
          <div>
            <Input
              label="Bot token"
              type="password"
              value={tgToken}
              onChange={(e) => setTgToken(e.target.value)}
              placeholder={data?.telegram_bot_token_set ? "•••••• (leave blank to keep)" : "1234567890:ABCdef…"}
            />
            {data?.telegram_bot_token_set && (
              <div className="mt-1.5">
                <Badge tone="pos" dot>Token is set</Badge>
              </div>
            )}
            <p className="mt-1.5 text-2xs text-ink-muted">
              Create a bot via @BotFather and paste the token here.
            </p>
          </div>
          <div>
            <Input
              label="Chat ID"
              value={tgChatId}
              onChange={(e) => setTgChatId(e.target.value)}
              placeholder="e.g. -1001234567890 or your user ID"
            />
            <p className="mt-1.5 text-2xs text-ink-muted">
              Your personal chat ID or a group/channel ID. Use @userinfobot to find yours.
            </p>
          </div>
          <div className="flex items-center gap-3 pt-1">
            <Button type="submit" disabled={tgBusy}>
              {tgBusy ? "Saving…" : "Save"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              disabled={!tgFullyConfigured || tgTestBusy}
              onClick={onTelegramTest}
              title={!tgFullyConfigured ? "Configure bot token and chat ID first" : undefined}
            >
              {tgTestBusy ? "Sending…" : "Send test"}
            </Button>
            {tgStatus && <span className="text-xs text-pos">{tgStatus}</span>}
            {tgError && <span className="text-xs text-neg">{tgError}</span>}
          </div>
        </form>
      </Card>
    </div>
  );
}
