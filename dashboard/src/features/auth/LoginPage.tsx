import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../../stores/authStore";
import { AuthLayout } from "../../layouts/AuthLayout";
import { Card } from "../../components/ui/Card";
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
      <Card>
        <h1 className="mb-4 text-lg font-semibold">Sign in</h1>
        <form onSubmit={onSubmit} className="space-y-4">
          <Input
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
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
          {error && <p className="text-sm text-kite-red">{error}</p>}
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </Card>
    </AuthLayout>
  );
}
