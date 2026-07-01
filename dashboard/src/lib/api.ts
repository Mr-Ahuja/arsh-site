import axios, { AxiosError } from "axios";

// One axios instance for the whole app.
export const http = axios.create({
  baseURL: "/api",
  withCredentials: true,
});

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[1]) : null;
}

// Attach the CSRF token (double-submit) on every mutating request.
http.interceptors.request.use((config) => {
  const method = (config.method ?? "get").toLowerCase();
  if (["post", "put", "patch", "delete"].includes(method)) {
    const csrf = readCookie("csrf");
    if (csrf) config.headers["X-CSRF-Token"] = csrf;
  }
  return config;
});

export interface ApiError {
  code: string;
  message: string;
}

// Response envelope: { ok, data, error }. Unwrap to data; normalize errors.
http.interceptors.response.use(
  (response) => {
    const body = response.data;
    if (body && typeof body === "object" && "ok" in body) {
      if (body.ok) {
        response.data = body.data;
        return response;
      }
      return Promise.reject(body.error as ApiError);
    }
    return response;
  },
  (error: AxiosError<{ error?: ApiError }>) => {
    const apiErr = error.response?.data?.error;
    if (apiErr) return Promise.reject(apiErr);
    return Promise.reject({ code: "network_error", message: error.message } as ApiError);
  },
);

// Typed helpers returning the unwrapped data.
export async function apiGet<T>(url: string): Promise<T> {
  return (await http.get<T>(url)).data;
}
export async function apiPost<T>(url: string, body?: unknown): Promise<T> {
  return (await http.post<T>(url, body)).data;
}
export async function apiPut<T>(url: string, body?: unknown): Promise<T> {
  return (await http.put<T>(url, body)).data;
}
export async function apiDelete<T>(url: string): Promise<T> {
  return (await http.delete<T>(url)).data;
}
