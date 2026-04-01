import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout } from '@/components/Layout';
import { ErrorAlert, EmptyState } from '@/components/Common';
import { apiClient } from '@/api/client';
import { Document } from '@/types';
import { formatDistanceToNow } from 'date-fns';

// ── Ingestion progress bar ────────────────────────────────────────────────────

type IngestionStage = 'uploading' | 'pending' | 'processing' | 'ready' | 'failed';

interface IngestionState {
  docId: string;
  filename: string;
  stage: IngestionStage;
  chunkCount: number;
  errorMessage: string;
}

const STAGE_PROGRESS: Record<IngestionStage, number> = {
  uploading: 15,
  pending: 35,
  processing: 65,
  ready: 100,
  failed: 100,
};

const STAGE_LABEL: Record<IngestionStage, string> = {
  uploading: 'Uploading file…',
  pending: 'Queued for processing…',
  processing: 'Chunking & embedding…',
  ready: 'Ingestion complete',
  failed: 'Ingestion failed',
};

const IngestionProgressBar: React.FC<{ state: IngestionState; onDismiss: () => void }> = ({
  state,
  onDismiss,
}) => {
  const progress = STAGE_PROGRESS[state.stage];
  const isDone = state.stage === 'ready' || state.stage === 'failed';
  const isFailed = state.stage === 'failed';

  return (
    <div
      className={`rounded-xl border p-5 shadow-sm transition-all ${
        isFailed
          ? 'border-red-200 bg-red-50'
          : state.stage === 'ready'
          ? 'border-green-200 bg-green-50'
          : 'border-blue-200 bg-blue-50'
      }`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <p
            className={`font-semibold text-sm ${
              isFailed ? 'text-red-800' : state.stage === 'ready' ? 'text-green-800' : 'text-blue-800'
            }`}
          >
            {state.filename}
          </p>
          <p
            className={`text-xs mt-0.5 ${
              isFailed ? 'text-red-600' : state.stage === 'ready' ? 'text-green-600' : 'text-blue-600'
            }`}
          >
            {STAGE_LABEL[state.stage]}
          </p>
        </div>

        {isDone && (
          <button
            onClick={onDismiss}
            className={`text-lg leading-none ml-4 ${
              isFailed ? 'text-red-400 hover:text-red-600' : 'text-green-400 hover:text-green-600'
            }`}
          >
            ✕
          </button>
        )}
      </div>

      {/* Progress bar */}
      <div className="h-2.5 rounded-full bg-gray-200 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ease-in-out ${
            isFailed
              ? 'bg-red-500'
              : state.stage === 'ready'
              ? 'bg-green-500'
              : 'bg-blue-500'
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Status detail */}
      <div className="flex items-center justify-between mt-2">
        <div className="flex gap-4">
          {(['uploading', 'pending', 'processing', 'ready'] as IngestionStage[]).map((s) => {
            const reached =
              STAGE_PROGRESS[state.stage] >= STAGE_PROGRESS[s] && !isFailed;
            return (
              <span
                key={s}
                className={`text-xs font-medium ${
                  reached ? 'text-blue-700' : 'text-gray-400'
                } ${state.stage === s && !isDone ? 'animate-pulse' : ''}`}
              >
                {s === 'uploading' ? '① Upload' : s === 'pending' ? '② Queue' : s === 'processing' ? '③ Process' : '④ Done'}
              </span>
            );
          })}
        </div>
        <span
          className={`text-xs font-semibold ${
            isFailed ? 'text-red-700' : state.stage === 'ready' ? 'text-green-700' : 'text-blue-700'
          }`}
        >
          {progress}%
        </span>
      </div>

      {/* Completion message */}
      {state.stage === 'ready' && (
        <div className="mt-3 flex items-center gap-2 bg-green-100 rounded-lg px-3 py-2">
          <span className="text-green-600 text-lg">✓</span>
          <p className="text-sm text-green-800 font-medium">
            Document ready!{' '}
            {state.chunkCount > 0 && (
              <span className="font-bold">{state.chunkCount} chunks</span>
            )}{' '}
            indexed and available for queries.
          </p>
        </div>
      )}

      {/* Error message */}
      {isFailed && (
        <div className="mt-3 flex items-center gap-2 bg-red-100 rounded-lg px-3 py-2">
          <span className="text-red-600 text-lg">✕</span>
          <p className="text-sm text-red-800">
            {state.errorMessage || 'Ingestion failed. Please try again.'}
          </p>
        </div>
      )}
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [jurisdiction, setJurisdiction] = useState('');
  const [ingestion, setIngestion] = useState<IngestionState | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Auto-poll interval for the documents table when any doc is processing
  const tablePollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    loadDocuments();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (tablePollRef.current) clearInterval(tablePollRef.current);
    };
  }, []);

  // Start/stop auto-refresh of the whole document list whenever processing docs exist
  useEffect(() => {
    const hasProcessing = documents.some(
      (d) => d.status === 'processing' || d.status === 'pending'
    );

    if (hasProcessing && !tablePollRef.current) {
      tablePollRef.current = setInterval(async () => {
        try {
          const res = await apiClient.listDocuments();
          setDocuments(res.documents);
          const stillProcessing = res.documents.some(
            (d) => d.status === 'processing' || d.status === 'pending'
          );
          if (!stillProcessing && tablePollRef.current) {
            clearInterval(tablePollRef.current);
            tablePollRef.current = null;
          }
        } catch { /* ignore */ }
      }, 3000);
    }

    if (!hasProcessing && tablePollRef.current) {
      clearInterval(tablePollRef.current);
      tablePollRef.current = null;
    }
  }, [documents]);

  const loadDocuments = async () => {
    setIsLoading(true);
    try {
      const response = await apiClient.listDocuments();
      setDocuments(response.documents);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load documents');
    } finally {
      setIsLoading(false);
    }
  };

  const startPolling = (docId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(async () => {
      try {
        const doc = await apiClient.getDocument(docId);

        setIngestion((prev) =>
          prev ? { ...prev, stage: doc.status as IngestionStage, chunkCount: doc.chunk_count || 0, errorMessage: doc.error_message || '' } : prev
        );

        if (doc.status === 'ready' || doc.status === 'failed') {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          loadDocuments();
        }
      } catch { /* silently retry */ }
    }, 1500);
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIsUploading(true);
    setError('');
    setIngestion({ docId: '', filename: file.name, stage: 'uploading', chunkCount: 0, errorMessage: '' });

    try {
      const result = await apiClient.uploadDocument(file, jurisdiction || undefined);

      setIngestion({ docId: result.document_id, filename: file.name, stage: 'pending', chunkCount: 0, errorMessage: '' });
      setFile(null);
      setJurisdiction('');

      startPolling(result.document_id);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upload document');
      setIngestion(null);
    } finally {
      setIsUploading(false);
    }
  };

  const handleResetStuck = async () => {
    try {
      const result = await apiClient.resetStuckDocuments();
      if (result.reset > 0) {
        loadDocuments();
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset stuck documents');
    }
  };

  const handleDelete = async (docId: string) => {
    if (!confirm('Delete this document? This action cannot be undone.')) return;
    try {
      await apiClient.deleteDocument(docId);
      loadDocuments();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete document');
    }
  };

  return (
    <Layout>
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold text-gray-900">Dashboard</h1>
            <p className="text-gray-600 mt-2">Manage your legal documents and view analysis</p>
          </div>
          <div className="flex gap-3">
            {documents.some(d => d.status === 'processing' || d.status === 'pending') && (
              <button
                onClick={handleResetStuck}
                className="px-4 py-2 text-sm font-medium text-amber-700 bg-amber-50 border border-amber-300 rounded-lg hover:bg-amber-100"
                title="Mark stuck processing documents as failed so they can be re-uploaded"
              >
                Reset Stuck
              </button>
            )}
            <button onClick={() => navigate('/query')} className="btn-primary">
              Ask a Question
            </button>
          </div>
        </div>

        {error && <ErrorAlert message={error} onDismiss={() => setError('')} />}

        {/* Ingestion progress */}
        {ingestion && (
          <IngestionProgressBar
            state={ingestion}
            onDismiss={() => setIngestion(null)}
          />
        )}

        {/* Upload form */}
        <div className="card">
          <h2 className="text-2xl font-semibold text-gray-900 mb-6">Upload Document</h2>

          <form onSubmit={handleUpload} className="space-y-4">
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

            <button
              type="submit"
              disabled={isUploading || !file}
              className="w-full btn-primary"
            >
              {isUploading ? 'Uploading…' : 'Upload Document'}
            </button>
          </form>
        </div>

        {/* Documents list */}
        <div className="card">
          <h2 className="text-2xl font-semibold text-gray-900 mb-6">Your Documents</h2>

          {isLoading ? (
            <div className="flex items-center gap-3 text-gray-500 py-4">
              <div className="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm">Loading documents…</span>
            </div>
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
                        {doc.status === 'processing' || doc.status === 'pending' ? (
                          <span className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                            <span className="w-3 h-3 rounded-full border-2 border-amber-400 border-t-transparent animate-spin" />
                            {doc.status}
                          </span>
                        ) : doc.status === 'ready' ? (
                          <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                            ✓ ready
                          </span>
                        ) : (
                          <div>
                            <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-red-50 text-red-700 border border-red-200">
                              ✕ failed
                            </span>
                            {doc.error_message && (
                              <p className="text-xs text-red-600 mt-1 max-w-[220px] leading-tight">
                                {doc.error_message}
                              </p>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{doc.chunk_count || '—'}</td>
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
