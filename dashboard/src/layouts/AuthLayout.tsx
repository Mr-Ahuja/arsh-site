import type { ReactNode } from "react";
import { Brand } from "../components/Brand";
import { ThemeToggle } from "../components/ThemeToggle";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-surface-alt">
      <header className="flex h-12 items-center justify-between border-b border-line bg-surface px-4">
        <Brand />
        <ThemeToggle />
      </header>
      <div className="flex flex-1 items-center justify-center px-4">
        <div className="w-full max-w-[340px] pb-16">{children}</div>
      </div>
    </div>
  );
}
