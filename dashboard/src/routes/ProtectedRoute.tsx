import { useEffect } from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import { connectEngineWs, disconnectEngineWs } from "../stores/engineStore";

export function ProtectedRoute({ children }: { children: JSX.Element }) {
  const { user, checked, fetchMe } = useAuthStore();

  useEffect(() => {
    if (!checked) void fetchMe();
  }, [checked, fetchMe]);

  // Start WS connection once authenticated; tear down on logout.
  useEffect(() => {
    if (user) {
      connectEngineWs();
    } else {
      disconnectEngineWs();
    }
    return () => {
      if (!user) disconnectEngineWs();
    };
  }, [user]);

  if (!checked) {
    return <div className="p-8 text-center text-ink-muted">Loading…</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
