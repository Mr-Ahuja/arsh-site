import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "ghost";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const base =
  "inline-flex items-center justify-center rounded px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";

const variants: Record<Variant, string> = {
  primary: "bg-kite-blue text-white hover:bg-[#2f6fb8]",
  ghost: "border border-line bg-white text-ink hover:bg-bg-alt",
};

export function Button({ variant = "primary", className = "", ...props }: Props) {
  return <button className={`${base} ${variants[variant]} ${className}`} {...props} />;
}
