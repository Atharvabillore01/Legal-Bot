import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout } from '@/components/Layout';
import { LoadingSpinner, ErrorAlert, SuccessAlert, EmptyState } from '@/components/Common';
import { apiClient } from '@/api/client';
import { formatDistanceToNow } from 'date-fns';
export const DashboardPage = () => {
    const navigate = useNavigate();
    const [documents, setDocuments] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [file, setFile] = useState(null);
    const [docName, setDocName] = useState('');
    const [jurisdiction, setJurisdiction] = useState('');
    // Load documents on mount
    useEffect(() => {
        loadDocuments();
    }, []);
    const loadDocuments = async () => {
        setIsLoading(true);
        setError('');
        try {
            const response = await apiClient.listDocuments();
            setDocuments(response.documents);
        }
        catch (err) {
            setError(err.response?.data?.error?.message || 'Failed to load documents');
        }
        finally {
            setIsLoading(false);
        }
    };
    const handleUpload = async (e) => {
        e.preventDefault();
        if (!file) {
            setError('Please select a file');
            return;
        }
        setIsUploading(true);
        setError('');
        try {
            await apiClient.uploadDocument(file, docName || file.name, jurisdiction || undefined);
            setSuccess('Document uploaded successfully! Processing...');
            setFile(null);
            setDocName('');
            setJurisdiction('');
            // Reload documents
            setTimeout(() => loadDocuments(), 2000);
        }
        catch (err) {
            setError(err.response?.data?.error?.message || 'Failed to upload document');
        }
        finally {
            setIsUploading(false);
        }
    };
    const handleDelete = async (docId) => {
        if (!confirm('Delete this document? This action cannot be undone.'))
            return;
        try {
            await apiClient.deleteDocument(docId);
            setSuccess('Document deleted successfully');
            loadDocuments();
        }
        catch (err) {
            setError(err.response?.data?.error?.message || 'Failed to delete document');
        }
    };
    return (_jsx(Layout, { children: _jsxs("div", { className: "max-w-6xl mx-auto space-y-8", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsxs("div", { children: [_jsx("h1", { className: "text-4xl font-bold text-gray-900", children: "Dashboard" }), _jsx("p", { className: "text-gray-600 mt-2", children: "Manage your legal documents and view analysis" })] }), _jsx("button", { onClick: () => navigate('/query'), className: "btn-primary", children: "Ask a Question" })] }), error && _jsx(ErrorAlert, { message: error, onDismiss: () => setError('') }), success && _jsx(SuccessAlert, { message: success, onDismiss: () => setSuccess('') }), _jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-2xl font-semibold text-gray-900 mb-6", children: "Upload Document" }), _jsxs("form", { onSubmit: handleUpload, className: "space-y-4", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-sm font-medium text-gray-700 mb-2", children: "Document File (PDF, DOCX, TXT)" }), _jsx("input", { type: "file", accept: ".pdf,.docx,.txt", onChange: (e) => setFile(e.target.files?.[0] || null), className: "w-full", required: true, disabled: isUploading }), file && (_jsxs("p", { className: "text-sm text-gray-600 mt-2", children: ["Selected: ", file.name, " (", (file.size / 1024 / 1024).toFixed(2), " MB)"] }))] }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-4", children: [_jsxs("div", { children: [_jsx("label", { htmlFor: "docName", className: "block text-sm font-medium text-gray-700 mb-2", children: "Document Name (Optional)" }), _jsx("input", { id: "docName", type: "text", value: docName, onChange: (e) => setDocName(e.target.value), className: "input-field", placeholder: "e.g., Indemnity Agreement", disabled: isUploading })] }), _jsxs("div", { children: [_jsx("label", { htmlFor: "jurisdiction", className: "block text-sm font-medium text-gray-700 mb-2", children: "Jurisdiction (Optional)" }), _jsx("input", { id: "jurisdiction", type: "text", value: jurisdiction, onChange: (e) => setJurisdiction(e.target.value), className: "input-field", placeholder: "e.g., NY", disabled: isUploading })] })] }), _jsx("button", { type: "submit", disabled: isUploading || !file, className: "w-full btn-primary", children: isUploading ? 'Uploading...' : 'Upload Document' })] })] }), _jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-2xl font-semibold text-gray-900 mb-6", children: "Your Documents" }), isLoading ? (_jsx(LoadingSpinner, { message: "Loading documents..." })) : documents.length === 0 ? (_jsx(EmptyState, { icon: "\uD83D\uDCC4", title: "No documents", description: "Upload a document to get started" })) : (_jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "w-full", children: [_jsx("thead", { className: "border-b border-gray-200 bg-gray-50", children: _jsxs("tr", { children: [_jsx("th", { className: "text-left px-4 py-3 font-semibold text-gray-900", children: "Name" }), _jsx("th", { className: "text-left px-4 py-3 font-semibold text-gray-900", children: "Type" }), _jsx("th", { className: "text-left px-4 py-3 font-semibold text-gray-900", children: "Status" }), _jsx("th", { className: "text-left px-4 py-3 font-semibold text-gray-900", children: "Chunks" }), _jsx("th", { className: "text-left px-4 py-3 font-semibold text-gray-900", children: "Uploaded" }), _jsx("th", { className: "text-left px-4 py-3 font-semibold text-gray-900", children: "Actions" })] }) }), _jsx("tbody", { children: documents.map((doc) => (_jsxs("tr", { className: "border-b border-gray-200 hover:bg-gray-50", children: [_jsxs("td", { className: "px-4 py-3", children: [_jsx("span", { className: "font-medium text-gray-900", children: doc.original_filename }), doc.jurisdiction && (_jsxs("span", { className: "text-sm text-gray-500 ml-2", children: ["(", doc.jurisdiction, ")"] }))] }), _jsx("td", { className: "px-4 py-3 text-sm text-gray-600", children: doc.file_type.toUpperCase() }), _jsx("td", { className: "px-4 py-3", children: _jsxs("span", { className: `text-sm px-3 py-1 rounded-full ${doc.status === 'ready'
                                                            ? 'bg-green-100 text-green-800'
                                                            : doc.status === 'processing' || doc.status === 'pending'
                                                                ? 'bg-yellow-100 text-yellow-800'
                                                                : 'bg-red-100 text-red-800'}`, children: [doc.status === 'processing' || doc.status === 'pending' ? '⏳ ' : doc.status === 'ready' ? '✓ ' : '✕ ', doc.status] }) }), _jsx("td", { className: "px-4 py-3 text-sm text-gray-600", children: doc.chunk_count || '-' }), _jsx("td", { className: "px-4 py-3 text-sm text-gray-600", children: formatDistanceToNow(new Date(doc.uploaded_at), { addSuffix: true }) }), _jsx("td", { className: "px-4 py-3 text-sm", children: _jsx("button", { onClick: () => handleDelete(doc.id), className: "text-red-600 hover:text-red-800 font-medium", children: "Delete" }) })] }, doc.id))) })] }) }))] })] }) }));
};
