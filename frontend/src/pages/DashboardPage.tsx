import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout } from '@/components/Layout';
import { LoadingSpinner, ErrorAlert, SuccessAlert, EmptyState } from '@/components/Common';
import { apiClient } from '@/api/client';
import { Document } from '@/types';
import { formatDistanceToNow } from 'date-fns';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [file, setFile] = useState<File | null>(null);
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
    } catch (err: any) {
      setError(err.response?.data?.error?.message || 'Failed to load documents');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a file');
      return;
    }

    setIsUploading(true);
    setError('');

    try {
      await apiClient.uploadDocument(
        file,
        jurisdiction || undefined,
      );
      setSuccess('Document uploaded successfully! Processing...');
      setFile(null);
      setJurisdiction('');

      // Reload documents
      setTimeout(() => loadDocuments(), 2000);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || 'Failed to upload document');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (docId: string) => {
    if (!confirm('Delete this document? This action cannot be undone.')) return;

    try {
      await apiClient.deleteDocument(docId);
      setSuccess('Document deleted successfully');
      loadDocuments();
    } catch (err: any) {
      setError(err.response?.data?.error?.message || 'Failed to delete document');
    }
  };

  return (
    <Layout>
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold text-gray-900">Dashboard</h1>
            <p className="text-gray-600 mt-2">Manage your legal documents and view analysis</p>
          </div>
          <button
            onClick={() => navigate('/query')}
            className="btn-primary"
          >
            Ask a Question
          </button>
        </div>

        {/* Alerts */}
        {error && <ErrorAlert message={error} onDismiss={() => setError('')} />}
        {success && <SuccessAlert message={success} onDismiss={() => setSuccess('')} />}

        {/* Upload Section */}
        <div className="card">
          <h2 className="text-2xl font-semibold text-gray-900 mb-6">Upload Document</h2>

          <form onSubmit={handleUpload} className="space-y-4">
            {/* File Input */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Document File (PDF, DOCX, TXT)
              </label>
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="w-full"
                required
                disabled={isUploading}
              />
              {file && (
                <p className="text-sm text-gray-600 mt-2">
                  Selected: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
                </p>
              )}
            </div>

            {/* Jurisdiction */}
            <div>
              <label htmlFor="jurisdiction" className="block text-sm font-medium text-gray-700 mb-2">
                Jurisdiction (Optional)
              </label>
              <input
                id="jurisdiction"
                type="text"
                value={jurisdiction}
                onChange={(e) => setJurisdiction(e.target.value)}
                className="input-field"
                placeholder="e.g., NY, CA, Federal"
                disabled={isUploading}
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isUploading || !file}
              className="w-full btn-primary"
            >
              {isUploading ? 'Uploading...' : 'Upload Document'}
            </button>
          </form>
        </div>

        {/* Documents List */}
        <div className="card">
          <h2 className="text-2xl font-semibold text-gray-900 mb-6">Your Documents</h2>

          {isLoading ? (
            <LoadingSpinner message="Loading documents..." />
          ) : documents.length === 0 ? (
            <EmptyState
              icon="📄"
              title="No documents"
              description="Upload a document to get started"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b border-gray-200 bg-gray-50">
                  <tr>
                    <th className="text-left px-4 py-3 font-semibold text-gray-900">Name</th>
                    <th className="text-left px-4 py-3 font-semibold text-gray-900">Type</th>
                    <th className="text-left px-4 py-3 font-semibold text-gray-900">Status</th>
                    <th className="text-left px-4 py-3 font-semibold text-gray-900">Chunks</th>
                    <th className="text-left px-4 py-3 font-semibold text-gray-900">Uploaded</th>
                    <th className="text-left px-4 py-3 font-semibold text-gray-900">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc: Document) => (
                    <tr key={doc.id} className="border-b border-gray-200 hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <span className="font-medium text-gray-900">{doc.original_filename}</span>
                        {doc.jurisdiction && (
                          <span className="text-sm text-gray-500 ml-2">({doc.jurisdiction})</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{doc.file_type.toUpperCase()}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-sm px-3 py-1 rounded-full ${
                            doc.status === 'ready'
                              ? 'bg-green-100 text-green-800'
                              : doc.status === 'processing' || doc.status === 'pending'
                                ? 'bg-yellow-100 text-yellow-800'
                                : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {doc.status === 'processing' || doc.status === 'pending' ? '⏳ ' : doc.status === 'ready' ? '✓ ' : '✕ '}
                          {doc.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{doc.chunk_count || '-'}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {formatDistanceToNow(new Date(doc.uploaded_at), { addSuffix: true })}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="text-red-600 hover:text-red-800 font-medium"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};
