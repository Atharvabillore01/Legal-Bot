import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useAuthStore from '@/store/authStore';
import { ErrorAlert } from '@/components/Common';
export const LoginPage = () => {
    const navigate = useNavigate();
    const { login, isLoading, error, clearError } = useAuthStore();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await login(email, password);
            navigate('/dashboard');
        }
        catch (err) {
            console.error('Login failed:', err);
        }
    };
    return (_jsx("div", { className: "min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100", children: _jsxs("div", { className: "w-full max-w-md", children: [_jsxs("div", { className: "text-center mb-8", children: [_jsx("div", { className: "text-6xl mb-4", children: "\u2696\uFE0F" }), _jsx("h1", { className: "text-3xl font-bold text-gray-900", children: "LegalBot" }), _jsx("p", { className: "text-gray-600 mt-2", children: "AI-Powered Legal Document Review" })] }), _jsxs("div", { className: "bg-white rounded-lg shadow-xl p-8", children: [error && (_jsx(ErrorAlert, { message: error, onDismiss: () => clearError() })), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-6", children: [_jsxs("div", { children: [_jsx("label", { htmlFor: "email", className: "block text-sm font-medium text-gray-700 mb-2", children: "Email Address" }), _jsx("input", { id: "email", type: "email", value: email, onChange: (e) => setEmail(e.target.value), className: "input-field", placeholder: "user@example.com", required: true })] }), _jsxs("div", { children: [_jsx("label", { htmlFor: "password", className: "block text-sm font-medium text-gray-700 mb-2", children: "Password" }), _jsx("input", { id: "password", type: "password", value: password, onChange: (e) => setPassword(e.target.value), className: "input-field", placeholder: "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022", required: true })] }), _jsx("button", { type: "submit", disabled: isLoading, className: "w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed", children: isLoading ? 'Logging in...' : 'Log In' })] }), _jsxs("div", { className: "mt-8 p-4 bg-blue-50 rounded-lg border border-blue-200", children: [_jsx("p", { className: "text-xs font-semibold text-blue-900 mb-2", children: "Demo Credentials:" }), _jsxs("p", { className: "text-xs text-blue-700", children: [_jsx("strong", { children: "Email:" }), " user@example.com", _jsx("br", {}), _jsx("strong", { children: "Password:" }), " password123"] })] })] }), _jsxs("p", { className: "text-center text-sm text-gray-600 mt-6", children: ["Don't have an account?", ' ', _jsx("a", { href: "/register", className: "text-blue-600 hover:underline font-medium", children: "Register" })] }), _jsx("p", { className: "text-center text-gray-500 text-xs mt-3", children: "Protected by legal-grade encryption. All data is confidential." })] }) }));
};
