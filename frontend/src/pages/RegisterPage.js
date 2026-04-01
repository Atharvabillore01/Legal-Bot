import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import useAuthStore from '@/store/authStore';
import { ErrorAlert } from '@/components/Common';
export const RegisterPage = () => {
    const navigate = useNavigate();
    const { register, isLoading, error, clearError } = useAuthStore();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [fullName, setFullName] = useState('');
    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await register(email, password, fullName || undefined);
            navigate('/dashboard');
        }
        catch {
            // error shown via store
        }
    };
    return (_jsx("div", { className: "min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100", children: _jsxs("div", { className: "w-full max-w-md", children: [_jsxs("div", { className: "text-center mb-8", children: [_jsx("div", { className: "text-6xl mb-4", children: "\u2696\uFE0F" }), _jsx("h1", { className: "text-3xl font-bold text-gray-900", children: "LegalBot" }), _jsx("p", { className: "text-gray-600 mt-2", children: "Create your account" })] }), _jsxs("div", { className: "bg-white rounded-lg shadow-xl p-8", children: [error && _jsx(ErrorAlert, { message: error, onDismiss: clearError }), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-5", children: [_jsxs("div", { children: [_jsx("label", { htmlFor: "fullName", className: "block text-sm font-medium text-gray-700 mb-2", children: "Full Name (Optional)" }), _jsx("input", { id: "fullName", type: "text", value: fullName, onChange: (e) => setFullName(e.target.value), className: "input-field", placeholder: "Jane Smith" })] }), _jsxs("div", { children: [_jsx("label", { htmlFor: "email", className: "block text-sm font-medium text-gray-700 mb-2", children: "Email Address" }), _jsx("input", { id: "email", type: "email", value: email, onChange: (e) => setEmail(e.target.value), className: "input-field", placeholder: "user@lawfirm.com", required: true })] }), _jsxs("div", { children: [_jsxs("label", { htmlFor: "password", className: "block text-sm font-medium text-gray-700 mb-2", children: ["Password ", _jsx("span", { className: "text-gray-400 font-normal", children: "(min 8 characters)" })] }), _jsx("input", { id: "password", type: "password", value: password, onChange: (e) => setPassword(e.target.value), className: "input-field", placeholder: "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022", minLength: 8, required: true })] }), _jsx("button", { type: "submit", disabled: isLoading, className: "w-full btn-primary", children: isLoading ? 'Creating account...' : 'Create Account' })] }), _jsxs("p", { className: "text-center text-sm text-gray-600 mt-6", children: ["Already have an account?", ' ', _jsx(Link, { to: "/login", className: "text-blue-600 hover:underline font-medium", children: "Log in" })] })] })] }) }));
};
