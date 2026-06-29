import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "ghost" | "subtle" | "danger";
type Size = "sm" | "md";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const base =
  "inline-flex items-center justify-center gap-1.5 rounded font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40";

const sizes: Record<Size, string> = {
  sm: "h-7 px-2.5 text-xs",
  md: "h-9 px-4 text-sm",
};

const variants: Record<Variant, string> = {
  primary: "bg-brand text-white hover:brightness-95",
  ghost: "border border-line text-ink hover:bg-surface-hover",
  subtle: "text-ink-soft hover:bg-surface-hover",
  danger: "bg-sell text-white hover:brightness-95",
};

export function Button({ variant = "primary", size = "md", className = "", ...props }: Props) {
  return (
    <button className={`${base} ${sizes[size]} ${variants[variant]} ${className}`} {...props} />
  );
}
