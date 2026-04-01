import React from 'react';

export interface ConfidenceInfo {
  score: number;
  level: 'LOW' | 'MEDIUM' | 'HIGH';
  interpretation?: string;
}

interface ConfidenceBadgeProps {
  confidence: ConfidenceInfo;
  size?: 'sm' | 'md' | 'lg';
}

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({ confidence, size = 'md' }) => {
  const config = {
    HIGH:   { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', icon: '✓' },
    MEDIUM: { bg: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-200',   icon: '△' },
    LOW:    { bg: 'bg-red-50',     text: 'text-red-700',     border: 'border-red-200',     icon: '!' },
  }[confidence.level];

  const sizeClass = { sm: 'text-xs px-2 py-0.5', md: 'text-sm px-2.5 py-1', lg: 'text-sm px-3 py-1.5' }[size];

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-semibold rounded-full border ${config.bg} ${config.text} ${config.border} ${sizeClass}`}
      title={confidence.interpretation}
    >
      <span>{config.icon}</span>
      <span>{confidence.level} {(confidence.score * 100).toFixed(0)}%</span>
    </span>
  );
};

interface DisclaimerProps { confidence: ConfidenceInfo; }

export const ConfidenceDisclaimer: React.FC<DisclaimerProps> = ({ confidence }) => {
  if (confidence.level === 'HIGH') return null;

  const isLow = confidence.level === 'LOW';
  return (
    <div className={`flex gap-3 p-4 rounded-lg border ${
      isLow ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'
    }`}>
      <span className={`text-lg shrink-0 ${isLow ? 'text-red-500' : 'text-amber-500'}`}>
        {isLow ? '⚠' : '△'}
      </span>
      <div>
        <p className={`font-semibold text-sm ${isLow ? 'text-red-800' : 'text-amber-800'}`}>
          {isLow ? 'Low confidence' : 'Medium confidence'} — {(confidence.score * 100).toFixed(0)}%
        </p>
        <p className={`text-xs mt-0.5 ${isLow ? 'text-red-700' : 'text-amber-700'}`}>
          {isLow
            ? 'Retrieved documents may not fully support this answer. Do not rely on it for legal decisions — consult qualified counsel.'
            : 'Verify key claims against the source documents before acting on this answer.'}
        </p>
      </div>
    </div>
  );
};
