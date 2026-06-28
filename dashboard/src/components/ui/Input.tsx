import type { InputHTMLAttributes } from "react";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export function Input({ label, className = "", id, ...props }: Props) {
  return (
    <label className="block">
      {label && <span className="mb-1 block text-sm text-ink">{label}</span>}
      <input
        id={id}
        className={`w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-kite-blue ${className}`}
        {...props}
      />
    </label>
  );
}
