import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link, useNavigate } from 'react-router-dom';
import useAuthStore from '@/store/authStore';
export const Layout = ({ children }) => {
    const navigate = useNavigate();
    const { user, logout } = useAuthStore();
    const handleLogout = async () => {
        await logout();
        navigate('/login');
    };
    return (_jsxs("div", { className: "min-h-screen flex flex-col", children: [_jsx("header", { className: "bg-blue-600 text-white shadow-lg", children: _jsxs("div", { className: "max-w-7xl mx-auto px-4 py-4 flex items-center justify-between", children: [_jsxs(Link, { to: "/dashboard", className: "flex items-center gap-2 text-2xl font-bold", children: [_jsx("span", { children: "\u2696\uFE0F" }), _jsx("span", { children: "LegalBot" })] }), _jsxs("nav", { className: "hidden md:flex gap-8", children: [_jsx(Link, { to: "/dashboard", className: "hover:text-blue-100 transition-colors", children: "Dashboard" }), _jsx(Link, { to: "/query", className: "hover:text-blue-100 transition-colors", children: "Query Documents" }), _jsx(Link, { to: "/audit-log", className: "hover:text-blue-100 transition-colors", children: "Audit Log" })] }), _jsxs("div", { className: "flex items-center gap-4", children: [_jsx("span", { className: "hidden sm:inline text-blue-100", children: user?.email }), _jsx("button", { onClick: handleLogout, className: "px-4 py-2 bg-red-500 rounded hover:bg-red-600 transition-colors", children: "Logout" })] })] }) }), _jsx("main", { className: "flex-1 bg-gray-50", children: _jsx("div", { className: "max-w-7xl mx-auto px-4 py-8", children: children }) }), _jsx("footer", { className: "bg-gray-900 text-gray-300 py-8 mt-12", children: _jsxs("div", { className: "max-w-7xl mx-auto px-4 text-center", children: [_jsx("p", { children: "LegalBot \u00A9 2024 - AI-Powered Legal Document Review" }), _jsx("p", { className: "text-sm text-gray-500 mt-2", children: "Always consult with qualified legal counsel for legal advice." })] }) })] }));
};
