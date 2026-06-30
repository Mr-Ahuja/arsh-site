import type { ReactNode } from "react";

type Tone = "default" | "pos" | "neg";

const valueTone: Record<Tone, string> = {
  default: "text-ink",
  pos: "text-pos",
  neg: "text-neg",
};

export function StatTile({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: Tone;
}) {
  return (
    <div className="rounded border border-line bg-surface px-3.5 py-3">
      <div className="text-2xs uppercase tracking-wide text-ink-muted">{label}</div>
      <div className={`num mt-1 text-lg font-semibold leading-none ${valueTone[tone]}`}>{value}</div>
      {sub && <div className="num mt-1 text-2xs text-ink-muted">{sub}</div>}
    </div>
  );
}
