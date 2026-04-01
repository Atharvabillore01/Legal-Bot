import React, { useState, useEffect } from 'react';
import { Layout } from '@/components/Layout';
import { LoadingSpinner, ErrorAlert, EmptyState } from '@/components/Common';
import { apiClient } from '@/api/client';
import { AuditLogEntry } from '@/types';
import { formatDistanceToNow } from 'date-fns';

const ACTION_COLORS: Record<string, string> = {
  query: 'bg-blue-100 text-blue-800',
  ingest: 'bg-green-100 text-green-800',
  delete: 'bg-red-100 text-red-800',
  login: 'bg-gray-100 text-gray-700',
  logout: 'bg-gray-100 text-gray-700',
};

export const AuditLogPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
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
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load audit log');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { loadLogs(); }, [page, actionFilter]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <Layout>
      <div className="max-w-6xl mx-auto space-y-6">
        <div>
          <h1 className="text-4xl font-bold text-gray-900">Audit Log</h1>
          <p className="text-gray-600 mt-1">Your complete activity history</p>
        </div>

        {error && <ErrorAlert message={error} onDismiss={() => setError('')} />}

        {/* Filters */}
        <div className="card flex items-center gap-4">
          <label className="text-sm font-medium text-gray-700">Filter by action:</label>
          <select
            value={actionFilter}
            onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
            className="input-field w-auto"
          >
            <option value="">All actions</option>
            <option value="query">Query</option>
            <option value="ingest">Ingest</option>
            <option value="delete">Delete</option>
            <option value="login">Login</option>
            <option value="logout">Logout</option>
          </select>
          <span className="ml-auto text-sm text-gray-500">{total} total entries</span>
        </div>

        {/* Table */}
        <div className="card overflow-x-auto p-0">
          {isLoading ? (
            <div className="p-8"><LoadingSpinner message="Loading audit log..." /></div>
          ) : logs.length === 0 ? (
            <div className="p-8">
              <EmptyState icon="📋" title="No activity yet" description="Your actions will appear here" />
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-semibold text-gray-900">Action</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-900">Resource</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-900">Details</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-900">Status</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-900">Latency</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-900">When</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${ACTION_COLORS[log.action] ?? 'bg-gray-100 text-gray-700'}`}>
                        {log.action}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {log.resource_type || '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-600 max-w-xs truncate">
                      {log.details?.query
                        ? <span title={log.details.query}>{String(log.details.query).slice(0, 60)}{String(log.details.query).length > 60 ? '…' : ''}</span>
                        : log.resource_id
                        ? <span className="font-mono text-xs">{log.resource_id.slice(0, 8)}…</span>
                        : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${log.status === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                        {log.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {log.latency_ms != null ? `${Math.round(log.latency_ms)}ms` : '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {formatDistanceToNow(new Date(log.created_at), { addSuffix: true })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-secondary disabled:opacity-40"
            >
              Previous
            </button>
            <span className="text-sm text-gray-600">Page {page} of {totalPages}</span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="btn-secondary disabled:opacity-40"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </Layout>
  );
};
