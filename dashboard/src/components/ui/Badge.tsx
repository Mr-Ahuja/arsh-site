import type { ReactNode } from "react";

type Tone = "pos" | "neg" | "muted" | "brand" | "warn";

const tones: Record<Tone, string> = {
  pos: "bg-pos-bg text-pos",
  neg: "bg-neg-bg text-neg",
  brand: "bg-brand-bg text-brand",
  warn: "bg-warn-bg text-warn",
  muted: "bg-surface-hover text-ink-muted",
};

export function Badge({
  tone = "muted",
  children,
  dot = false,
}: {
  tone?: Tone;
  children: ReactNode;
  dot?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-2xs font-medium ${tones[tone]}`}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}
