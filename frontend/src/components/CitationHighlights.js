import { jsxs as _jsxs, jsx as _jsx } from "react/jsx-runtime";
import { useState } from 'react';
export const CitationHighlights = ({ citations, }) => {
    const [expandedCitation, setExpandedCitation] = useState(null);
    return (_jsx("div", { className: "space-y-4", children: _jsxs("div", { className: "bg-blue-50 border border-blue-200 rounded-lg p-4", children: [_jsxs("h3", { className: "font-semibold text-blue-900 mb-3", children: ["Citations (", citations.length, ")"] }), citations.length === 0 ? (_jsx("p", { className: "text-sm text-blue-700", children: "No citations in response" })) : (_jsx("div", { className: "space-y-2", children: citations.map((citation, idx) => (_jsxs("div", { className: "bg-white border border-blue-100 rounded p-3 cursor-pointer hover:shadow-md transition-shadow", onClick: () => setExpandedCitation(expandedCitation === citation.chunk_id ? null : citation.chunk_id), children: [_jsxs("div", { className: "flex items-start justify-between", children: [_jsxs("div", { className: "flex-1", children: [_jsxs("div", { className: "font-medium text-sm text-gray-900", children: [citation.source_doc, citation.page_number && _jsxs("span", { className: "text-gray-500 ml-2", children: ["p.", citation.page_number] })] }), citation.section && (_jsx("div", { className: "text-xs text-gray-600 mt-1", children: _jsx("strong", { children: citation.section }) })), citation.jurisdiction && (_jsxs("div", { className: "text-xs text-gray-500", children: ["Jurisdiction: ", citation.jurisdiction] }))] }), _jsx("span", { className: "text-lg", children: expandedCitation === citation.chunk_id ? '▼' : '▶' })] }), expandedCitation === citation.chunk_id && (_jsxs("div", { className: "mt-3 pt-3 border-t border-blue-100", children: [_jsxs("p", { className: "text-sm text-gray-700 italic", children: ["\"", citation.text_excerpt, "\""] }), _jsxs("div", { className: "text-xs text-gray-500 mt-2", children: ["Characters ", citation.character_offset_start, "-", citation.character_offset_end] })] }))] }, idx))) }))] }) }));
};
export const HighlightedAnswer = ({ answer, citations }) => {
    // Parse [[CITE:chunk_id]] markers and highlight
    const parts = [];
    const citationRegex = /\[\[CITE:([a-z0-9_]+)\]\]/g;
    let lastIndex = 0;
    let match;
    while ((match = citationRegex.exec(answer)) !== null) {
        // Add text before citation
        if (match.index > lastIndex) {
            parts.push({ text: answer.substring(lastIndex, match.index) });
        }
        // Find matching citation
        const chunkId = match[1];
        const citationIdx = citations.findIndex((c) => c.chunk_id === chunkId);
        if (citationIdx >= 0) {
            parts.push({ text: `[${citationIdx + 1}]`, citationIndex: citationIdx });
        }
        lastIndex = citationRegex.lastIndex;
    }
    // Add remaining text
    if (lastIndex < answer.length) {
        parts.push({ text: answer.substring(lastIndex) });
    }
    return (_jsx("div", { className: "text-lg leading-relaxed", children: parts.map((part, idx) => (part.citationIndex !== undefined ? (_jsx("sup", { className: "bg-blue-200 text-blue-900 px-1.5 py-0.5 rounded text-sm font-medium ml-1", children: part.text }, idx)) : (_jsx("span", { children: part.text }, idx)))) }));
};
