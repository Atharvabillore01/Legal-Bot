import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Citation } from '@/types';

interface HighlightedAnswerProps {
  answer: string;
  citations: Citation[];
}

/**
 * Renders the LLM answer as Markdown.
 *
 * [[CITE:chunk_id]] markers are replaced with superscript [N] badges.
 * The badge number corresponds to the citation's position in the citations array.
 */
export const HighlightedAnswer: React.FC<HighlightedAnswerProps> = ({ answer, citations }) => {
  // Build a lookup: chunk_id → 1-based citation number
  const citationIndex: Record<string, number> = {};
  citations.forEach((c, i) => {
    citationIndex[c.chunk_id] = i + 1;
  });

  // Replace [[CITE:chunk_id]] with [N]
  const processed = answer.replace(/\[\[CITE:([a-zA-Z0-9_\-]+)\]\]/g, (_match, chunkId) => {
    const num = citationIndex[chunkId];
    return num != null ? `[${num}]` : '';
  });

  return (
    <div className="text-base leading-relaxed text-gray-900 prose prose-blue max-w-none">
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="mb-4 leading-relaxed">{children}</p>,
          h1: ({ children }) => <h1 className="text-2xl font-bold mt-6 mb-3">{children}</h1>,
          h2: ({ children }) => <h2 className="text-xl font-bold mt-5 mb-2">{children}</h2>,
          h3: ({ children }) => <h3 className="text-lg font-semibold mt-4 mb-2">{children}</h3>,
          ul: ({ children }) => <ul className="list-disc list-inside mb-4 space-y-1 ml-2">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal list-inside mb-4 space-y-1 ml-2">{children}</ol>,
          li: ({ children }) => <li className="mb-1">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-blue-400 pl-4 py-1 mb-4 italic text-gray-700 bg-blue-50 rounded-r">
              {children}
            </blockquote>
          ),
          strong: ({ children }) => <strong className="font-bold text-gray-900">{children}</strong>,
          em: ({ children }) => <em className="italic text-gray-800">{children}</em>,
          code: ({ children, className }) =>
            className?.includes('language-') ? (
              <pre className="bg-gray-900 text-gray-100 p-4 rounded mb-4 overflow-x-auto">
                <code className="text-sm font-mono">{children}</code>
              </pre>
            ) : (
              <code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm font-mono text-red-700">{children}</code>
            ),
          table: ({ children }) => (
            <div className="overflow-x-auto mb-4">
              <table className="border-collapse border border-gray-300 w-full text-sm">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-gray-100">{children}</thead>,
          th: ({ children }) => (
            <th className="border border-gray-300 px-3 py-2 text-left font-semibold">{children}</th>
          ),
          td: ({ children }) => <td className="border border-gray-300 px-3 py-2">{children}</td>,
          hr: () => <hr className="my-6 border-gray-300" />,
          a: ({ href, children }) => (
            <a href={href} className="text-blue-600 underline hover:text-blue-800">
              {children}
            </a>
          ),
          // Render inline text — intercept [N] patterns to render as superscript badges
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          text: ({ children }: any) => {
            const text = String(children);
            const parts: React.ReactNode[] = [];
            let last = 0;
            const re = /\[(\d+)\]/g;
            let m: RegExpExecArray | null;
            while ((m = re.exec(text)) !== null) {
              if (m.index > last) parts.push(text.slice(last, m.index));
              parts.push(
                <sup
                  key={`c-${m.index}`}
                  className="inline-flex items-center justify-center bg-blue-600 text-white rounded-full w-4 h-4 text-[10px] font-bold ml-0.5 align-super"
                  title={`Citation ${m[1]}`}
                >
                  {m[1]}
                </sup>
              );
              last = m.index + m[0].length;
            }
            if (last < text.length) parts.push(text.slice(last));
            return parts.length > 1 ? <>{parts}</> : <>{children}</>;
          },
        }}
      >
        {processed}
      </ReactMarkdown>
    </div>
  );
};
