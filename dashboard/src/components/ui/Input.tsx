import { forwardRef, type InputHTMLAttributes } from "react";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export const Input = forwardRef<HTMLInputElement, Props>(function Input(
  { label, className = "", id, ...props },
  ref,
) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1 block text-xs font-medium text-ink-soft">{label}</span>
      )}
      <input
        ref={ref}
        id={id}
        className={`h-9 w-full rounded border border-line bg-surface px-3 text-sm text-ink placeholder:text-ink-muted outline-none transition-colors focus:border-brand ${className}`}
        {...props}
      />
    </label>
  );
});
