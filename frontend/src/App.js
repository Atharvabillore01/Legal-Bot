import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { QueryPage } from '@/pages/QueryPage';
import { AuditLogPage } from '@/pages/AuditLogPage';
import useAuthStore from '@/store/authStore';
// Restores session on first render, shows nothing until resolved
function SessionLoader({ children }) {
    const { restoreSession } = useAuthStore();
    const [ready, setReady] = React.useState(false);
    useEffect(() => {
        restoreSession().finally(() => setReady(true));
    }, []);
    if (!ready) {
        return (_jsx("div", { className: "min-h-screen flex items-center justify-center bg-gray-50", children: _jsx("div", { className: "text-gray-500 text-lg", children: "Loading..." }) }));
    }
    return _jsx(_Fragment, { children: children });
}
// Redirect to /login if not authenticated
function RequireAuth({ children }) {
    const { isAuthenticated } = useAuthStore();
    const location = useLocation();
    if (!isAuthenticated) {
        return _jsx(Navigate, { to: "/login", state: { from: location }, replace: true });
    }
    return _jsx(_Fragment, { children: children });
}
// Redirect to /dashboard if already logged in
function RedirectIfAuth({ children }) {
    const { isAuthenticated } = useAuthStore();
    if (isAuthenticated)
        return _jsx(Navigate, { to: "/dashboard", replace: true });
    return _jsx(_Fragment, { children: children });
}
export default function App() {
    return (_jsx(BrowserRouter, { children: _jsx(SessionLoader, { children: _jsxs(Routes, { children: [_jsx(Route, { path: "/login", element: _jsx(RedirectIfAuth, { children: _jsx(LoginPage, {}) }) }), _jsx(Route, { path: "/register", element: _jsx(RedirectIfAuth, { children: _jsx(RegisterPage, {}) }) }), _jsx(Route, { path: "/dashboard", element: _jsx(RequireAuth, { children: _jsx(DashboardPage, {}) }) }), _jsx(Route, { path: "/query", element: _jsx(RequireAuth, { children: _jsx(QueryPage, {}) }) }), _jsx(Route, { path: "/audit-log", element: _jsx(RequireAuth, { children: _jsx(AuditLogPage, {}) }) }), _jsx(Route, { path: "/", element: _jsx(Navigate, { to: "/dashboard", replace: true }) }), _jsx(Route, { path: "*", element: _jsx(Navigate, { to: "/dashboard", replace: true }) })] }) }) }));
}
