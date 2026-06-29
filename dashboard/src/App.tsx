import { Routes, Route, Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { ProtectedRoute } from "./routes/ProtectedRoute";
import { AppLayout } from "./layouts/AppLayout";
import { LoginPage } from "./features/auth/LoginPage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { KiteConnect } from "./features/auth/KiteConnect";
import { CockpitPage } from "./features/cockpit/CockpitPage";
import { Placeholder } from "./features/Placeholder";

function Protected({ children, rail = true }: { children: ReactNode; rail?: boolean }) {
  return (
    <ProtectedRoute>
      <AppLayout rail={rail}>{children}</AppLayout>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Protected><CockpitPage /></Protected>} />
      <Route
        path="/history"
        element={
          <Protected>
            <Placeholder title="Orders" note="Order history & trade journal arrive in Task 10." />
          </Protected>
        }
      />
      <Route
        path="/analytics"
        element={
          <Protected>
            <Placeholder title="Analytics" note="Equity curve, drawdown & metrics arrive in Task 11." />
          </Protected>
        }
      />
      <Route
        path="/backtest"
        element={
          <Protected>
            <Placeholder title="Backtest" note="The backtest runner arrives in Task 12." />
          </Protected>
        }
      />
      <Route path="/settings" element={<Protected rail={false}><SettingsPage /></Protected>} />
      <Route path="/connect" element={<Protected rail={false}><KiteConnect /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
