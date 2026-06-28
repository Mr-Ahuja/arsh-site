import type { ReactNode } from "react";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-alt px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="text-xl font-semibold text-kite-blue">Trade Engine</div>
          <div className="text-sm text-ink-muted">Intraday algo dashboard</div>
        </div>
        {children}
      </div>
    </div>
  );
}
