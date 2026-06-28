import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "./routes/ProtectedRoute";
import { AppLayout } from "./layouts/AppLayout";
import { LoginPage } from "./features/auth/LoginPage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { KiteConnect } from "./features/auth/KiteConnect";
import { CockpitPage } from "./features/cockpit/CockpitPage";
import type { ReactNode } from "react";

function Protected({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <AppLayout>{children}</AppLayout>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Protected><CockpitPage /></Protected>} />
      <Route path="/settings" element={<Protected><SettingsPage /></Protected>} />
      <Route path="/connect" element={<Protected><KiteConnect /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
