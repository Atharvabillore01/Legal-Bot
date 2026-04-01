import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { QueryPage } from '@/pages/QueryPage';
import { AuditLogPage } from '@/pages/AuditLogPage';
import useAuthStore from '@/store/authStore';

// Restores session on first render, shows nothing until resolved
function SessionLoader({ children }: { children: React.ReactNode }) {
  const { restoreSession } = useAuthStore();
  const [ready, setReady] = React.useState(false);

  useEffect(() => {
    restoreSession().finally(() => setReady(true));
  }, []);

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-gray-500 text-lg">Loading...</div>
      </div>
    );
  }

  return <>{children}</>;
}

// Redirect to /login if not authenticated
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}

// Redirect to /dashboard if already logged in
function RedirectIfAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <SessionLoader>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<RedirectIfAuth><LoginPage /></RedirectIfAuth>} />
          <Route path="/register" element={<RedirectIfAuth><RegisterPage /></RedirectIfAuth>} />

          {/* Protected */}
          <Route path="/dashboard" element={<RequireAuth><DashboardPage /></RequireAuth>} />
          <Route path="/query" element={<RequireAuth><QueryPage /></RequireAuth>} />
          <Route path="/audit-log" element={<RequireAuth><AuditLogPage /></RequireAuth>} />

          {/* Default */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </SessionLoader>
    </BrowserRouter>
  );
}
