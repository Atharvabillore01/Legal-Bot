import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export const ConfidenceBadge = ({ confidence, size = 'md' }) => {
    const getBadgeClass = () => {
        const base = 'rounded-full font-semibold flex items-center gap-2';
        const sizeClasses = {
            sm: 'px-2 py-1 text-xs',
            md: 'px-3 py-1.5 text-sm',
            lg: 'px-4 py-2 text-base',
        };
        const colorClasses = {
            HIGH: 'bg-green-100 text-green-800',
            MEDIUM: 'bg-yellow-100 text-yellow-800',
            LOW: 'bg-red-100 text-red-800',
        };
        return `${base} ${sizeClasses[size]} ${colorClasses[confidence.level]}`;
    };
    const getIcon = () => {
        switch (confidence.level) {
            case 'HIGH':
                return '✓';
            case 'MEDIUM':
                return '⚠';
            case 'LOW':
                return '✕';
        }
    };
    return (_jsxs("div", { className: getBadgeClass(), title: confidence.interpretation, children: [_jsx("span", { children: getIcon() }), _jsxs("span", { children: [confidence.level, " (", (confidence.score * 100).toFixed(0), "%)"] })] }));
};
export const ConfidenceDisclaimer = ({ confidence }) => {
    if (confidence.level !== 'LOW') {
        return null;
    }
    return (_jsx("div", { className: "border-l-4 border-red-500 bg-red-50 p-4 rounded", children: _jsxs("div", { className: "flex gap-3", children: [_jsx("span", { className: "text-2xl", children: "\u26A0\uFE0F" }), _jsxs("div", { children: [_jsx("h3", { className: "font-bold text-red-800 mb-1", children: "Low Confidence Answer" }), _jsxs("p", { className: "text-red-700 text-sm mb-2", children: ["This answer has low confidence (", (confidence.score * 100).toFixed(0), "%). The retrieved documents may not fully support this answer."] }), _jsxs("p", { className: "text-red-700 text-sm font-semibold", children: [_jsx("strong", { children: "Do NOT rely on this answer for legal decisions." }), "Always consult with qualified legal counsel and review source documents directly."] })] })] }) }));
};
