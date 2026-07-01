import { Routes, Route, Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { ProtectedRoute } from "./routes/ProtectedRoute";
import { AppLayout } from "./layouts/AppLayout";
import { LoginPage } from "./features/auth/LoginPage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { KiteConnect } from "./features/auth/KiteConnect";
import { CockpitPage } from "./features/cockpit/CockpitPage";
import { DocsPage } from "./features/docs/DocsPage";
import { HistoryPage } from "./features/history/HistoryPage";
import { AnalyticsPage } from "./features/analytics/AnalyticsPage";
import { BacktestPage } from "./features/backtest/BacktestPage";
import { StrategyEditorPage } from "./features/strategies/StrategyEditorPage";

function Protected({
  children,
  rail = true,
  noPad = false,
}: {
  children: ReactNode;
  rail?: boolean;
  noPad?: boolean;
}) {
  return (
    <ProtectedRoute>
      <AppLayout rail={rail} noPad={noPad}>{children}</AppLayout>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Protected><CockpitPage /></Protected>} />
      <Route path="/history" element={<Protected><HistoryPage /></Protected>} />
      <Route path="/analytics" element={<Protected><AnalyticsPage /></Protected>} />
      <Route path="/backtest" element={<Protected><BacktestPage /></Protected>} />
      <Route path="/strategies" element={<Protected rail={false} noPad><StrategyEditorPage /></Protected>} />
      <Route path="/settings" element={<Protected rail={false}><SettingsPage /></Protected>} />
      <Route path="/connect" element={<Protected rail={false}><KiteConnect /></Protected>} />
      {/* Docs — no rail, no padding; DocsPage manages its own sidebar and scroll */}
      <Route
        path="/docs"
        element={<Protected rail={false} noPad><DocsPage /></Protected>}
      />
      <Route
        path="/docs/:slug"
        element={<Protected rail={false} noPad><DocsPage /></Protected>}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
