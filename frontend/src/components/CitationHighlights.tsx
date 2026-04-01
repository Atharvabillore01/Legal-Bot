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

  // Normalize inline markdown: LLM sometimes outputs headings/bullets on one line.
  // Strategy: split on heading/bullet markers, then rejoin with proper newlines.
  const normalized = (() => {
    let t = processed;

    // 1. Force every heading onto its own line (handles # ## ### etc.)
    //    Works even when no newline precedes the marker.
    t = t.replace(/(#{1,6})\s+/g, '\n\n$1 ');

    // 2. Force list items onto their own line.
    //    A bullet is " - " or " * " surrounded by spaces (not inside **bold**).
    t = t.replace(/\s+-\s+(?=[A-Z\w])/g, '\n- ');

    // 3. Strip stray leading/trailing * and # that the LLM emits as decorators.
    //    e.g. "**Heading**" in the middle of a line → keep bold, just ensure newline before it.
    t = t.replace(/\s\*\*([^*]+)\*\*\s*-\s*/g, '\n\n**$1**\n- ');

    // 4. Collapse runs of 3+ newlines to double newline.
    t = t.replace(/\n{3,}/g, '\n\n');

    return t.trim();
  })();

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
        {normalized}
      </ReactMarkdown>
    </div>
  );
};
