import { create } from "zustand";
import { apiGet, apiPost } from "../lib/api";

interface User {
  username: string;
}

interface AuthState {
  user: User | null;
  checked: boolean; // whether /me has been attempted
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  fetchMe: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  checked: false,
  async login(username, password) {
    const user = await apiPost<User>("/auth/login", { username, password });
    set({ user, checked: true });
  },
  async logout() {
    try {
      await apiPost("/auth/logout");
    } finally {
      set({ user: null });
    }
  },
  async fetchMe() {
    try {
      const user = await apiGet<User>("/auth/me");
      set({ user, checked: true });
    } catch {
      set({ user: null, checked: true });
    }
  },
}));
