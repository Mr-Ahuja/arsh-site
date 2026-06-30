import { useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../lib/api";
import { useAuthStore } from "../stores/authStore";
import { Brand } from "../components/Brand";
import { ThemeToggle } from "../components/ThemeToggle";
import { Watchlist } from "../components/Watchlist";
import { Badge } from "../components/ui/Badge";

interface KiteStatus {
  connected: boolean;
  user_id: string | null;
  valid_for_date: string | null;
}

const navItems = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/history", label: "Orders" },
  { to: "/analytics", label: "Analytics" },
  { to: "/backtest", label: "Backtest" },
  { to: "/settings", label: "Settings" },
];

function IndexPill({ name }: { name: string }) {
  // Placeholder until the live feed lands (Task 03).
  return (
    <span className="hidden items-center gap-1.5 lg:inline-flex" title="Live values arrive with the tick feed (Task 03)">
      <span className="text-2xs font-medium text-ink-muted">{name}</span>
      <span className="num text-xs text-ink-soft">—</span>
    </span>
  );
}

function ProfileMenu() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const initial = (user?.username ?? "?").charAt(0).toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded px-1.5 py-1 hover:bg-surface-hover"
      >
        <span className="grid h-7 w-7 place-items-center rounded-full bg-brand-bg text-xs font-semibold text-brand">
          {initial}
        </span>
        <span className="hidden text-xs font-medium text-ink-soft sm:block">{user?.username}</span>
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-1 w-40 rounded border border-line bg-surface py-1 shadow-lg">
          <button
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
            className="block w-full px-3 py-1.5 text-left text-xs text-ink-soft hover:bg-surface-hover"
          >
            Logout
          </button>
        </div>
      )}
    </div>
  );
}

export function AppLayout({ children, rail = true }: { children: ReactNode; rail?: boolean }) {
  const { data: kite } = useQuery({
    queryKey: ["kite-status"],
    queryFn: () => apiGet<KiteStatus>("/kite/status"),
    refetchInterval: 60_000,
  });

  return (
    <div className="flex h-screen flex-col bg-surface-alt">
      {/* ── Top navigation ─────────────────────────────────────────────── */}
      <header className="flex h-12 shrink-0 items-center gap-4 border-b border-line bg-surface px-4">
        <Brand />
        <div className="ml-2 flex items-center gap-4 border-l border-line pl-4">
          <IndexPill name="NIFTY 50" />
          <IndexPill name="SENSEX" />
        </div>

        <nav className="ml-auto flex items-center gap-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `rounded px-2.5 py-1.5 text-xs font-medium transition-colors ${
                  isActive ? "text-brand" : "text-ink-soft hover:bg-surface-hover"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-1.5 border-l border-line pl-3">
          <NavLink to="/connect" title="Kite connection">
            {kite?.connected ? (
              <Badge tone="pos" dot>
                {kite.user_id}
              </Badge>
            ) : (
              <Badge tone="neg" dot>
                Not connected
              </Badge>
            )}
          </NavLink>
          <ThemeToggle />
          <ProfileMenu />
        </div>
      </header>

      {/* ── Workspace ──────────────────────────────────────────────────── */}
      <div className="flex min-h-0 flex-1">
        {rail && <Watchlist />}
        <main className="min-w-0 flex-1 overflow-y-auto p-4">{children}</main>
      </div>
    </div>
  );
}
