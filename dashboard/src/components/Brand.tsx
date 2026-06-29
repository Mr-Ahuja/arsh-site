export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2 select-none">
      {/* Diamond/kite mark */}
      <span className="grid h-6 w-6 place-items-center rounded-sm bg-brand">
        <span className="h-2.5 w-2.5 rotate-45 border-[1.5px] border-white" />
      </span>
      {!compact && <span className="text-sm font-semibold tracking-tight text-ink">Trade Engine</span>}
    </span>
  );
}
