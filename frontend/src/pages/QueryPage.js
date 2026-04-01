import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { Layout } from '@/components/Layout';
import { ConfidenceBadge, ConfidenceDisclaimer } from '@/components/ConfidenceBadge';
import { CitationHighlights, HighlightedAnswer } from '@/components/CitationHighlights';
import { LoadingSpinner, ErrorAlert, EmptyState } from '@/components/Common';
import { apiClient } from '@/api/client';
import { formatDistanceToNow } from 'date-fns';
export const QueryPage = () => {
    const [query, setQuery] = useState('');
    const [k, setK] = useState(7);
    const [jurisdiction, setJurisdiction] = useState('');
    const [response, setResponse] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);
        try {
            const result = await apiClient.submitQuery(query, k, jurisdiction || undefined);
            setResponse(result);
            setQuery('');
        }
        catch (err) {
            setError(err.response?.data?.error?.message || 'Failed to submit query');
        }
        finally {
            setIsLoading(false);
        }
    };
    return (_jsx(Layout, { children: _jsxs("div", { className: "max-w-4xl mx-auto space-y-8", children: [_jsxs("div", { children: [_jsx("h1", { className: "text-4xl font-bold text-gray-900 mb-2", children: "Query Your Documents" }), _jsx("p", { className: "text-gray-600", children: "Ask questions about your uploaded legal documents. Answers are AI-generated and include citations." })] }), error && _jsx(ErrorAlert, { message: error, onDismiss: () => setError('') }), _jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-2xl font-semibold text-gray-900 mb-6", children: "Ask a Legal Question" }), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-6", children: [_jsxs("div", { children: [_jsx("label", { htmlFor: "query", className: "block text-sm font-medium text-gray-700 mb-2", children: "Your Question" }), _jsx("textarea", { id: "query", value: query, onChange: (e) => setQuery(e.target.value), className: "input-field min-h-24", placeholder: "E.g., 'What is the liability cap?', 'What are the payment terms?'", required: true }), _jsx("p", { className: "text-xs text-gray-500 mt-1", children: "Max 2000 characters" })] }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-4", children: [_jsxs("div", { children: [_jsx("label", { htmlFor: "k", className: "block text-sm font-medium text-gray-700 mb-2", children: "Number of Source Chunks" }), _jsx("input", { id: "k", type: "number", min: "1", max: "50", value: k, onChange: (e) => setK(Number(e.target.value)), className: "input-field" }), _jsx("p", { className: "text-xs text-gray-500 mt-1", children: "Default: 7" })] }), _jsxs("div", { children: [_jsx("label", { htmlFor: "jurisdiction", className: "block text-sm font-medium text-gray-700 mb-2", children: "Jurisdiction (Optional)" }), _jsx("input", { id: "jurisdiction", type: "text", value: jurisdiction, onChange: (e) => setJurisdiction(e.target.value), className: "input-field", placeholder: "e.g., NY, CA, TX" })] })] }), _jsx("button", { type: "submit", disabled: isLoading || !query.trim(), className: "w-full btn-primary", children: isLoading ? 'Searching...' : 'Submit Query' })] })] }), isLoading && _jsx(LoadingSpinner, { message: "Searching documents and generating answer..." }), response && !isLoading && (() => {
                    const confidence = {
                        score: response.confidence_score,
                        level: response.confidence_level,
                    };
                    return (_jsxs("div", { className: "space-y-6", children: [_jsx(ConfidenceDisclaimer, { confidence: confidence }), _jsxs("div", { className: "card", children: [_jsxs("div", { className: "flex items-start justify-between mb-4", children: [_jsx("h2", { className: "text-2xl font-semibold text-gray-900", children: "Answer" }), _jsx(ConfidenceBadge, { confidence: confidence, size: "lg" })] }), _jsx(HighlightedAnswer, { answer: response.answer, citations: response.citations }), _jsxs("div", { className: "mt-6 pt-6 border-t border-gray-200 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm", children: [_jsxs("div", { children: [_jsx("p", { className: "text-gray-600", children: "Model" }), _jsx("p", { className: "font-medium", children: response.model })] }), _jsxs("div", { children: [_jsx("p", { className: "text-gray-600", children: "Citations" }), _jsx("p", { className: "font-medium", children: response.citations.length })] }), _jsxs("div", { children: [_jsx("p", { className: "text-gray-600", children: "Search Time" }), _jsxs("p", { className: "font-medium", children: [Math.round(response.search_time_ms), "ms"] })] }), _jsxs("div", { children: [_jsx("p", { className: "text-gray-600", children: "Total Time" }), _jsxs("p", { className: "font-medium", children: [Math.round(response.total_time_ms), "ms"] })] })] })] }), _jsx(CitationHighlights, { citations: response.citations, answer: response.answer }), _jsxs("div", { className: "bg-gray-100 rounded-lg p-4 text-sm text-gray-600", children: [_jsxs("p", { children: [_jsx("strong", { children: "Timestamp:" }), " ", formatDistanceToNow(new Date(response.created_at), { addSuffix: true })] }), response.has_contradictions && (_jsx("p", { className: "mt-1 text-amber-700 font-medium", children: "\u26A0 Contradictions detected between source documents" }))] })] }));
                })(), !response && !isLoading && (_jsx(EmptyState, { icon: "\uD83D\uDCDD", title: "No queries yet", description: "Submit a question about your documents to get started" }))] }) }));
};
