import { useEffect } from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";

export function ProtectedRoute({ children }: { children: JSX.Element }) {
  const { user, checked, fetchMe } = useAuthStore();

  useEffect(() => {
    if (!checked) void fetchMe();
  }, [checked, fetchMe]);

  if (!checked) {
    return <div className="p-8 text-center text-ink-muted">Loading…</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
