import { Card } from "../components/ui/Card";

export function Placeholder({ title, note }: { title: string; note: string }) {
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <h1 className="text-base font-semibold text-ink">{title}</h1>
      <Card>
        <div className="py-12 text-center text-xs text-ink-muted">{note}</div>
      </Card>
    </div>
  );
}
