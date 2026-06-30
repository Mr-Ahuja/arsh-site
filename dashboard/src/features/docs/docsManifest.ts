export interface DocEntry {
  slug: string;
  title: string;
  file: string;
}

export const DOCS: DocEntry[] = [
  { slug: "getting-started", title: "Getting Started", file: "/docs/01-getting-started.md" },
  { slug: "cockpit", title: "Live Cockpit", file: "/docs/02-cockpit.md" },
  { slug: "settings", title: "Settings", file: "/docs/03-settings.md" },
  { slug: "orders", title: "Orders", file: "/docs/04-orders.md" },
  { slug: "analytics", title: "Analytics", file: "/docs/05-analytics.md" },
  { slug: "backtest", title: "Backtest", file: "/docs/06-backtest.md" },
  { slug: "go-live", title: "Go-Live Checklist", file: "/docs/07-go-live.md" },
];
