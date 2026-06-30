import { create } from "zustand";

type Theme = "light" | "dark";

function apply(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

const initial: Theme =
  (localStorage.getItem("theme") as Theme | null) ??
  (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light");

apply(initial); // run before first paint to avoid a flash

interface UiState {
  theme: Theme;
  toggleTheme: () => void;
}

export const useUiStore = create<UiState>((set, get) => ({
  theme: initial,
  toggleTheme() {
    const next: Theme = get().theme === "light" ? "dark" : "light";
    localStorage.setItem("theme", next);
    apply(next);
    set({ theme: next });
  },
}));
