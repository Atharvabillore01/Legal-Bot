import React, { useState, useRef, useEffect } from 'react';
import { Layout } from '@/components/Layout';
import { ConfidenceBadge, ConfidenceDisclaimer, ConfidenceInfo } from '@/components/ConfidenceBadge';
import { HighlightedAnswer } from '@/components/CitationHighlights';
import { LoadingSpinner, ErrorAlert, EmptyState } from '@/components/Common';
import { apiClient } from '@/api/client';
import { QueryResponse, SourceChunk } from '@/types';

// ── Source chunk card ─────────────────────────────────────────────────────────

const SourceCard: React.FC<{ chunk: SourceChunk; index: number }> = ({ chunk, index }) => {
  const [expanded, setExpanded] = useState(false);
  const score = Math.round(chunk.relevance_score * 100);

  return (
    <div className="border border-gray-200 rounded-lg bg-white overflow-hidden">
      {/* Header row */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-gray-50 transition-colors"
      >
        {/* Rank badge */}
        <span className="shrink-0 w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center mt-0.5">
          {index + 1}
        </span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-gray-900 text-sm truncate max-w-[200px]">
              {chunk.doc_name}
            </span>
            {chunk.page_number != null && (
              <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full font-medium">
                p.{chunk.page_number}
              </span>
            )}
            {chunk.jurisdiction && (
              <span className="text-xs bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full">
                {chunk.jurisdiction}
              </span>
            )}
          </div>
          {chunk.section && (
            <p className="text-xs text-gray-500 mt-0.5 truncate">{chunk.section}</p>
          )}
        </div>

        {/* Relevance score */}
        <div className="shrink-0 flex flex-col items-end gap-1">
          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
              score >= 70
                ? 'bg-green-100 text-green-800'
                : score >= 45
                ? 'bg-yellow-100 text-yellow-800'
                : 'bg-gray-100 text-gray-600'
            }`}
          >
            {score}%
          </span>
          <span className="text-gray-400 text-xs">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>

      {/* Expanded text */}
      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-gray-100">
          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
            {chunk.text}
          </p>
        </div>
      )}
    </div>
  );
};

// ── History entry ─────────────────────────────────────────────────────────────

interface HistoryItem {
  query: string;
  response: QueryResponse;
  timestamp: Date;
}

const HistoryEntry: React.FC<{
  item: HistoryItem;
  index: number;
  onRestore: (item: HistoryItem) => void;
}> = ({ item, onRestore }) => (
  <button
    onClick={() => onRestore(item)}
    className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors group"
  >
    <p className="text-sm text-gray-800 font-medium truncate group-hover:text-blue-700">
      {item.query}
    </p>
    <p className="text-xs text-gray-400 mt-0.5">
      {item.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
      {' · '}
      <span
        className={
          item.response.confidence_level === 'HIGH'
            ? 'text-green-600'
            : item.response.confidence_level === 'MEDIUM'
            ? 'text-yellow-600'
            : 'text-red-600'
        }
      >
        {item.response.confidence_level}
      </span>
    </p>
  </button>
);

// ── Main page ─────────────────────────────────────────────────────────────────

export const QueryPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [jurisdiction, setJurisdiction] = useState('');
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [activeTab, setActiveTab] = useState<'sources' | 'citations'>('sources');
  const answerRef = useRef<HTMLDivElement>(null);

  // Scroll to answer on new result
  useEffect(() => {
    if (response && answerRef.current) {
      answerRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [response]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setError('');
    setIsLoading(true);

    try {
      const result = await apiClient.submitQuery(query.trim(), 7, jurisdiction || undefined);
      setResponse(result);
      setHistory((prev) => [{ query: query.trim(), response: result, timestamp: new Date() }, ...prev].slice(0, 20));
      setActiveTab('sources');
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.error?.message || 'Failed to submit query');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRestoreHistory = (item: HistoryItem) => {
    setQuery(item.query);
    setResponse(item.response);
    setActiveTab('sources');
  };

  const confidence: ConfidenceInfo | null = response
    ? { score: response.confidence_score, level: response.confidence_level }
    : null;

  return (
    <Layout>
      <div className="max-w-7xl mx-auto flex gap-6">
        {/* ── Left sidebar: query + history ── */}
        <aside className="w-80 shrink-0 space-y-6">
          {/* Query form */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Ask a Question</h2>

            {error && <ErrorAlert message={error} onDismiss={() => setError('')} />}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="query" className="block text-sm font-medium text-gray-700 mb-1">
                  Your question
                </label>
                <textarea
                  id="query"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="input-field min-h-28 text-sm"
                  placeholder="e.g. What is the liability cap?"
                  required
                />
              </div>

              <div>
                <label htmlFor="jurisdiction" className="block text-sm font-medium text-gray-700 mb-1">
                  Jurisdiction (optional)
                </label>
                <input
                  id="jurisdiction"
                  type="text"
                  value={jurisdiction}
                  onChange={(e) => setJurisdiction(e.target.value)}
                  className="input-field text-sm"
                  placeholder="e.g. NY, CA, Federal"
                />
              </div>

              <button
                type="submit"
                disabled={isLoading || !query.trim()}
                className="w-full btn-primary"
              >
                {isLoading ? 'Searching…' : 'Submit Query'}
              </button>
            </form>
          </div>

          {/* Query history */}
          {history.length > 0 && (
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Recent queries</h3>
              <div className="space-y-1">
                {history.map((item, idx) => (
                  <HistoryEntry key={idx} item={item} index={idx} onRestore={handleRestoreHistory} />
                ))}
              </div>
            </div>
          )}
        </aside>

        {/* ── Main content ── */}
        <main className="flex-1 min-w-0 space-y-6">
          {/* Loading */}
          {isLoading && (
            <LoadingSpinner message="Searching documents and generating answer…" />
          )}

          {/* Result */}
          {response && !isLoading && (
            <div ref={answerRef} className="space-y-4">
              {/* Confidence disclaimer (LOW only) */}
              {confidence && <ConfidenceDisclaimer confidence={confidence} />}

              {/* Contradictions warning */}
              {response.has_contradictions && (
                <div className="border-l-4 border-yellow-500 bg-yellow-50 p-4 rounded">
                  <p className="text-yellow-800 font-semibold text-sm">
                    Contradictions detected across retrieved documents. Review sources carefully.
                  </p>
                </div>
              )}

              {/* Answer card */}
              <div className="card">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold text-gray-900">Answer</h2>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400">
                      {Math.round(response.total_time_ms)}ms · {response.model}
                    </span>
                    {confidence && <ConfidenceBadge confidence={confidence} size="md" />}
                  </div>
                </div>

                <HighlightedAnswer answer={response.answer} citations={response.citations} />
              </div>

              {/* Sources / Citations tabs */}
              <div className="card">
                {/* Tab bar */}
                <div className="flex gap-1 border-b border-gray-200 mb-4">
                  <button
                    onClick={() => setActiveTab('sources')}
                    className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
                      activeTab === 'sources'
                        ? 'bg-blue-50 text-blue-700 border-b-2 border-blue-600'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    Retrieved Sources ({response.source_chunks.length})
                  </button>
                  <button
                    onClick={() => setActiveTab('citations')}
                    className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
                      activeTab === 'citations'
                        ? 'bg-blue-50 text-blue-700 border-b-2 border-blue-600'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    Inline Citations ({response.citations.length})
                  </button>
                </div>

                {/* Sources tab */}
                {activeTab === 'sources' && (
                  <div className="space-y-2">
                    {response.source_chunks.length === 0 ? (
                      <p className="text-sm text-gray-500">No sources retrieved.</p>
                    ) : (
                      response.source_chunks.map((chunk, idx) => (
                        <SourceCard key={chunk.chunk_id} chunk={chunk} index={idx} />
                      ))
                    )}
                  </div>
                )}

                {/* Citations tab */}
                {activeTab === 'citations' && (
                  <div className="space-y-2">
                    {response.citations.length === 0 ? (
                      <p className="text-sm text-gray-500">No inline citations in this answer.</p>
                    ) : (
                      response.citations.map((citation, idx) => (
                        <div
                          key={idx}
                          className="border border-gray-200 rounded-lg p-3 bg-white"
                        >
                          <div className="flex items-start gap-3">
                            <sup className="bg-blue-200 text-blue-900 px-1.5 py-0.5 rounded text-xs font-bold mt-0.5">
                              {idx + 1}
                            </sup>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-medium text-sm text-gray-900">
                                  {citation.source_doc}
                                </span>
                                {citation.page_number != null && (
                                  <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full font-medium">
                                    p.{citation.page_number}
                                  </span>
                                )}
                                {citation.jurisdiction && (
                                  <span className="text-xs text-gray-500">
                                    {citation.jurisdiction}
                                  </span>
                                )}
                              </div>
                              {citation.section && (
                                <p className="text-xs text-gray-500 mt-0.5">{citation.section}</p>
                              )}
                              <blockquote className="mt-2 text-sm text-gray-700 italic border-l-2 border-blue-300 pl-3">
                                "{citation.text_excerpt}"
                              </blockquote>
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Empty state */}
          {!response && !isLoading && (
            <EmptyState
              icon="📝"
              title="No queries yet"
              description="Submit a question on the left to search your legal documents"
            />
          )}
        </main>
      </div>
    </Layout>
  );
};
