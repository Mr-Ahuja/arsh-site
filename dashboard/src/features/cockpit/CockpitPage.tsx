import { Card } from "../../components/ui/Card";

export function CockpitPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Cockpit</h1>
      <Card>
        <p className="text-sm text-ink-muted">
          The live cockpit (positions, P&L, kill-switch) arrives in Task 09. The shell, auth, and
          Kite connection are wired up now.
        </p>
      </Card>
    </div>
  );
}
