import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../lib/api";
import { useAuthStore } from "../stores/authStore";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";

interface KiteStatus {
  connected: boolean;
  user_id: string | null;
  valid_for_date: string | null;
}

const navItems = [
  { to: "/", label: "Cockpit", end: true },
  { to: "/history", label: "History" },
  { to: "/analytics", label: "Analytics" },
  { to: "/backtest", label: "Backtest" },
  { to: "/settings", label: "Settings" },
  { to: "/connect", label: "Connect" },
];

export function AppLayout({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);

  const { data: kite } = useQuery({
    queryKey: ["kite-status"],
    queryFn: () => apiGet<KiteStatus>("/kite/status"),
    refetchInterval: 60_000,
  });

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-bg-alt">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
          <span className="font-semibold text-kite-blue">Trade Engine</span>
          <nav className="flex gap-4 text-sm">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  isActive ? "text-kite-blue" : "text-ink-muted hover:text-ink"
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            {kite?.connected ? (
              <Badge tone="green">Kite: {kite.user_id}</Badge>
            ) : (
              <Badge tone="red">Kite: disconnected</Badge>
            )}
            <Button variant="ghost" onClick={handleLogout}>
              Logout
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
