/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Semantic colors map to CSS variables (see theme/tokens.css) so light/dark
      // swap with a single class on <html> and components stay theme-agnostic.
      colors: {
        canvas: "var(--canvas)",
        surface: "var(--surface)",
        "surface-alt": "var(--surface-alt)",
        "surface-hover": "var(--surface-hover)",
        line: "var(--line)",
        "line-strong": "var(--line-strong)",
        ink: "var(--ink)",
        "ink-soft": "var(--ink-soft)",
        "ink-muted": "var(--ink-muted)",
        brand: "var(--brand)",
        "brand-bg": "var(--brand-bg)",
        buy: "var(--buy)",
        sell: "var(--sell)",
        pos: "var(--pos)",
        neg: "var(--neg)",
        "pos-bg": "var(--pos-bg)",
        "neg-bg": "var(--neg-bg)",
        warn: "var(--warn)",
        "warn-bg": "var(--warn-bg)",
      },
      fontFamily: {
        sans: ["Inter", "IBM Plex Sans", "system-ui", "sans-serif"],
      },
      fontSize: {
        "2xs": ["11px", "14px"],
        xs: ["12px", "16px"],
        sm: ["13px", "18px"],
        base: ["14px", "20px"],
      },
      borderRadius: {
        DEFAULT: "3px",
      },
    },
  },
  plugins: [],
};
