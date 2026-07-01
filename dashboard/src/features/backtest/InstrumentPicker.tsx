import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../../lib/api";

export interface Instrument {
  instrument_token: number;
  exchange: string;
  tradingsymbol: string;
  name: string;
  label: string; // "NSE:KOTAKBANK"
}

const INPUT_CLS =
  "w-full rounded border border-line bg-surface-alt px-2.5 py-1.5 text-xs text-ink placeholder:text-ink-muted focus:outline-none focus:ring-1 focus:ring-brand";

type Exchange = "NSE" | "BSE";

/**
 * Searchable instrument picker. The user types to filter the DB-buffered Kite list
 * and MUST pick a row — free text alone never becomes a value (onChange(null) until
 * a selection is made).
 */
export function InstrumentPicker({
  value,
  onChange,
}: {
  value: Instrument | null;
  onChange: (i: Instrument | null) => void;
}) {
  const [exchange, setExchange] = useState<Exchange>("NSE");
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  // Keep the input text in sync when a value is set externally / cleared.
  useEffect(() => {
    if (value) setQuery(value.label);
  }, [value]);

  // Debounce the query.
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 220);
    return () => clearTimeout(t);
  }, [query]);

  // Close on outside click.
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const { data, isFetching } = useQuery({
    queryKey: ["instruments", exchange, debounced],
    queryFn: () =>
      apiGet<{ results: Instrument[] }>(
        `/instruments/search?exchange=${exchange}&limit=30&q=${encodeURIComponent(debounced)}`,
      ),
    enabled: open,
    staleTime: 60_000,
  });
  const results = data?.results ?? [];

  function select(inst: Instrument) {
    onChange(inst);
    setQuery(inst.label);
    setOpen(false);
  }

  function onInput(text: string) {
    setQuery(text);
    setOpen(true);
    setHighlight(0);
    if (value) onChange(null); // editing invalidates a prior selection
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (!open && (e.key === "ArrowDown" || e.key === "Enter")) {
      setOpen(true);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => Math.min(h + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (results[highlight]) select(results[highlight]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="relative" ref={boxRef}>
      <div className="flex gap-1.5">
        <select
          value={exchange}
          onChange={(e) => {
            setExchange(e.target.value as Exchange);
            if (value) onChange(null);
            setOpen(true);
          }}
          className="rounded border border-line bg-surface-alt px-1.5 py-1.5 text-xs text-ink focus:outline-none focus:ring-1 focus:ring-brand"
        >
          <option value="NSE">NSE</option>
          <option value="BSE">BSE</option>
        </select>
        <input
          value={query}
          onChange={(e) => onInput(e.target.value)}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder="Search symbol or company…"
          className={INPUT_CLS}
          autoComplete="off"
          required
        />
      </div>

      {/* Selection state hint */}
      {value ? (
        <p className="mt-1 truncate text-2xs text-pos">
          ✓ {value.label} — {value.name || value.tradingsymbol}
        </p>
      ) : (
        <p className="mt-1 text-2xs text-ink-muted">Pick an instrument from the list.</p>
      )}

      {open && (
        <div className="absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded border border-line bg-surface shadow-lg">
          {isFetching && !results.length && (
            <div className="px-3 py-2 text-2xs text-ink-muted">Searching…</div>
          )}
          {!isFetching && !results.length && (
            <div className="px-3 py-2 text-2xs text-ink-muted">
              {debounced ? "No matches." : "Type to search…"}
            </div>
          )}
          {results.map((r, i) => (
            <button
              key={`${r.exchange}:${r.tradingsymbol}`}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => select(r)}
              onMouseEnter={() => setHighlight(i)}
              className={`flex w-full items-baseline justify-between gap-2 px-3 py-1.5 text-left ${
                i === highlight ? "bg-brand-bg" : "hover:bg-surface-hover"
              }`}
            >
              <span className="font-mono text-xs text-ink">{r.tradingsymbol}</span>
              <span className="truncate text-2xs text-ink-muted">{r.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
