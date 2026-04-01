import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect } from 'react';
import { Layout } from '@/components/Layout';
import { LoadingSpinner, ErrorAlert, EmptyState } from '@/components/Common';
import { apiClient } from '@/api/client';
import { formatDistanceToNow } from 'date-fns';
const ACTION_COLORS = {
    query: 'bg-blue-100 text-blue-800',
    ingest: 'bg-green-100 text-green-800',
    delete: 'bg-red-100 text-red-800',
    login: 'bg-gray-100 text-gray-700',
    logout: 'bg-gray-100 text-gray-700',
};
export const AuditLogPage = () => {
    const [logs, setLogs] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [actionFilter, setActionFilter] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');
    const pageSize = 50;
    const loadLogs = async (p = page, action = actionFilter) => {
        setIsLoading(true);
        setError('');
        try {
            const resp = await apiClient.getAuditLog(p, pageSize, action || undefined);
            setLogs(resp.logs);
            setTotal(resp.total);
        }
        catch (err) {
            setError(err.response?.data?.detail || 'Failed to load audit log');
        }
        finally {
            setIsLoading(false);
        }
    };
    useEffect(() => { loadLogs(); }, [page, actionFilter]);
    const totalPages = Math.ceil(total / pageSize);
    return (_jsx(Layout, { children: _jsxs("div", { className: "max-w-6xl mx-auto space-y-6", children: [_jsxs("div", { children: [_jsx("h1", { className: "text-4xl font-bold text-gray-900", children: "Audit Log" }), _jsx("p", { className: "text-gray-600 mt-1", children: "Your complete activity history" })] }), error && _jsx(ErrorAlert, { message: error, onDismiss: () => setError('') }), _jsxs("div", { className: "card flex items-center gap-4", children: [_jsx("label", { className: "text-sm font-medium text-gray-700", children: "Filter by action:" }), _jsxs("select", { value: actionFilter, onChange: (e) => { setActionFilter(e.target.value); setPage(1); }, className: "input-field w-auto", children: [_jsx("option", { value: "", children: "All actions" }), _jsx("option", { value: "query", children: "Query" }), _jsx("option", { value: "ingest", children: "Ingest" }), _jsx("option", { value: "delete", children: "Delete" }), _jsx("option", { value: "login", children: "Login" }), _jsx("option", { value: "logout", children: "Logout" })] }), _jsxs("span", { className: "ml-auto text-sm text-gray-500", children: [total, " total entries"] })] }), _jsx("div", { className: "card overflow-x-auto p-0", children: isLoading ? (_jsx("div", { className: "p-8", children: _jsx(LoadingSpinner, { message: "Loading audit log..." }) })) : logs.length === 0 ? (_jsx("div", { className: "p-8", children: _jsx(EmptyState, { icon: "\uD83D\uDCCB", title: "No activity yet", description: "Your actions will appear here" }) })) : (_jsxs("table", { className: "w-full text-sm", children: [_jsx("thead", { className: "border-b border-gray-200 bg-gray-50", children: _jsxs("tr", { children: [_jsx("th", { className: "text-left px-4 py-3 font-semibold text-gray-900", children: "Action" }), _jsx("th", { className: "text-left px-4 py-3 font-semibold text-gray-900", children: "Resource" }), _jsx("th", { className: "text-left px-4 py-3 font-semibold text-gray-900", children: "Details" }), _jsx("th", { className: "text-left px-4 py-3 font-semibold text-gray-900", children: "Status" }), _jsx("th", { className: "text-left px-4 py-3 font-semibold text-gray-900", children: "Latency" }), _jsx("th", { className: "text-left px-4 py-3 font-semibold text-gray-900", children: "When" })] }) }), _jsx("tbody", { children: logs.map((log) => (_jsxs("tr", { className: "border-b border-gray-100 hover:bg-gray-50", children: [_jsx("td", { className: "px-4 py-3", children: _jsx("span", { className: `px-2 py-1 rounded-full text-xs font-medium ${ACTION_COLORS[log.action] ?? 'bg-gray-100 text-gray-700'}`, children: log.action }) }), _jsx("td", { className: "px-4 py-3 text-gray-600", children: log.resource_type || '—' }), _jsx("td", { className: "px-4 py-3 text-gray-600 max-w-xs truncate", children: log.details?.query
                                                ? _jsxs("span", { title: log.details.query, children: [String(log.details.query).slice(0, 60), String(log.details.query).length > 60 ? '…' : ''] })
                                                : log.resource_id
                                                    ? _jsxs("span", { className: "font-mono text-xs", children: [log.resource_id.slice(0, 8), "\u2026"] })
                                                    : '—' }), _jsx("td", { className: "px-4 py-3", children: _jsx("span", { className: `px-2 py-1 rounded-full text-xs font-medium ${log.status === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`, children: log.status }) }), _jsx("td", { className: "px-4 py-3 text-gray-600", children: log.latency_ms != null ? `${Math.round(log.latency_ms)}ms` : '—' }), _jsx("td", { className: "px-4 py-3 text-gray-500", children: formatDistanceToNow(new Date(log.created_at), { addSuffix: true }) })] }, log.id))) })] })) }), totalPages > 1 && (_jsxs("div", { className: "flex items-center justify-center gap-3", children: [_jsx("button", { onClick: () => setPage((p) => Math.max(1, p - 1)), disabled: page === 1, className: "btn-secondary disabled:opacity-40", children: "Previous" }), _jsxs("span", { className: "text-sm text-gray-600", children: ["Page ", page, " of ", totalPages] }), _jsx("button", { onClick: () => setPage((p) => Math.min(totalPages, p + 1)), disabled: page === totalPages, className: "btn-secondary disabled:opacity-40", children: "Next" })] }))] }) }));
};
