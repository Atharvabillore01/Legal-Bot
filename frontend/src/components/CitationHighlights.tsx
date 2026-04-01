import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Citation } from '@/types';

interface HighlightedAnswerProps {
  answer: string;
  citations: Citation[];
}

export const HighlightedAnswer: React.FC<HighlightedAnswerProps> = ({ answer, citations }) => {
  // Build lookup: chunk_id → 1-based number
  const citationIndex: Record<string, number> = {};
  citations.forEach((c, i) => { citationIndex[c.chunk_id] = i + 1; });

  // Strip [[CITE:...]] markers — capture chunk_id before any comma/space (LLM may add ", Page: X")
  const processed = answer.replace(/\[\[CITE:([^\]]+)\]\]/g, (_match, rawId) => {
    const chunkId = rawId.split(',')[0].trim();
    const num = citationIndex[chunkId];
    return num != null ? ` [${num}]` : '';
  });

  return (
    <div className="answer-prose">
      <ReactMarkdown
        components={{
          p: ({ children }) => <p>{children}</p>,
          h1: ({ children }) => <h1>{children}</h1>,
          h2: ({ children }) => <h2>{children}</h2>,
          h3: ({ children }) => <h3>{children}</h3>,
          ul: ({ children }) => <ul>{children}</ul>,
          ol: ({ children }) => <ol>{children}</ol>,
          li: ({ children }) => <li>{children}</li>,
          strong: ({ children }) => <strong>{children}</strong>,
          em: ({ children }) => <em>{children}</em>,
          blockquote: ({ children }) => <blockquote>{children}</blockquote>,
          hr: () => <hr />,
          table: ({ children }) => <div className="overflow-x-auto"><table>{children}</table></div>,
          thead: ({ children }) => <thead>{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children }) => <tr>{children}</tr>,
          th: ({ children }) => <th>{children}</th>,
          td: ({ children }) => <td>{children}</td>,
          code: ({ children, className }) =>
            className?.includes('language-') ? (
              <pre><code>{children}</code></pre>
            ) : (
              <code>{children}</code>
            ),
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
          ),
          // Render [N] citation numbers as superscript badges
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
                  className="inline-flex items-center justify-center bg-indigo-600 text-white rounded-full w-4 h-4 text-[9px] font-bold ml-0.5 cursor-default"
                  title={`Source ${m[1]}`}
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
