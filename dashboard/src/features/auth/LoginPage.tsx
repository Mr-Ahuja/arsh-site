import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../../stores/authStore";
import { AuthLayout } from "../../layouts/AuthLayout";
import { Input } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";
import type { ApiError } from "../../lib/api";

export function LoginPage() {
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError((err as ApiError).message ?? "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <div className="rounded-md border border-line bg-surface px-6 py-7 shadow-sm">
        <h1 className="text-base font-semibold text-ink">Login to your account</h1>
        <p className="mb-5 mt-1 text-xs text-ink-muted">Trade engine control panel</p>
        <form onSubmit={onSubmit} className="space-y-3.5">
          <Input
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
          {error && (
            <p className="rounded border border-neg/30 bg-neg-bg px-2.5 py-1.5 text-xs text-neg">
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? "Signing in…" : "Login"}
          </Button>
        </form>
      </div>
      <p className="mt-4 text-center text-2xs text-ink-muted">
        Single-user access · sessions expire after 8 hours
      </p>
    </AuthLayout>
  );
}
