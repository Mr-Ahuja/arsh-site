import type { ReactNode } from "react";

type Tone = "green" | "red" | "muted";

const tones: Record<Tone, string> = {
  green: "bg-kite-green/10 text-kite-green",
  red: "bg-kite-red/10 text-kite-red",
  muted: "bg-bg-alt text-ink-muted",
};

export function Badge({ tone = "muted", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}
