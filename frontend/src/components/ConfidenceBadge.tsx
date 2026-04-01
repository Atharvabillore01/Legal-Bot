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
  const getBadgeClass = () => {
    const base = 'rounded-full font-semibold flex items-center gap-2';
    const sizeClasses = {
      sm: 'px-2 py-1 text-xs',
      md: 'px-3 py-1.5 text-sm',
      lg: 'px-4 py-2 text-base',
    };
    const colorClasses = {
      HIGH: 'bg-green-100 text-green-800',
      MEDIUM: 'bg-yellow-100 text-yellow-800',
      LOW: 'bg-red-100 text-red-800',
    };
    return `${base} ${sizeClasses[size]} ${colorClasses[confidence.level]}`;
  };

  const getIcon = () => {
    switch (confidence.level) {
      case 'HIGH':
        return '✓';
      case 'MEDIUM':
        return '⚠';
      case 'LOW':
        return '✕';
    }
  };

  return (
    <div className={getBadgeClass()} title={confidence.interpretation}>
      <span>{getIcon()}</span>
      <span>{confidence.level} ({(confidence.score * 100).toFixed(0)}%)</span>
    </div>
  );
};

interface DisclaimerProps {
  confidence: ConfidenceInfo;
}

export const ConfidenceDisclaimer: React.FC<DisclaimerProps> = ({ confidence }) => {
  if (confidence.level === 'HIGH') return null;

  const isLow = confidence.level === 'LOW';

  return (
    <div
      className={`border-l-4 p-4 rounded ${
        isLow ? 'border-red-500 bg-red-50' : 'border-yellow-400 bg-yellow-50'
      }`}
    >
      <div className="flex gap-3">
        <span className="text-xl">{isLow ? '⚠️' : '⚡'}</span>
        <div>
          <h3 className={`font-bold mb-1 text-sm ${isLow ? 'text-red-800' : 'text-yellow-800'}`}>
            {isLow ? 'Low Confidence Answer' : 'Medium Confidence Answer'}
          </h3>
          <p className={`text-sm ${isLow ? 'text-red-700' : 'text-yellow-700'}`}>
            {isLow
              ? `Confidence is ${(confidence.score * 100).toFixed(0)}%. Retrieved documents may not fully support this answer.`
              : `Confidence is ${(confidence.score * 100).toFixed(0)}%. Verify key claims against source documents before relying on this answer.`}
          </p>
          {isLow && (
            <p className="text-red-700 text-sm font-semibold mt-1">
              Do NOT rely on this answer for legal decisions. Always consult qualified legal counsel.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
