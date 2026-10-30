import React from 'react';
import { Clock, FileText, X, Trash2 } from 'lucide-react';
import { RecentQuestion } from '../../types/api';

interface RecentQuestionsCardProps {
  questions: RecentQuestion[];
  onSelectQuestion: (question: string, ticker: string) => void;
  onRemoveQuestion: (id: string) => void;
  onClearAll: () => void;
}

export const RecentQuestionsCard: React.FC<RecentQuestionsCardProps> = ({
  questions,
  onSelectQuestion,
  onRemoveQuestion,
  onClearAll,
}) => {
  const formatRelativeTime = (timestamp: number) => {
    const diffSeconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
    if (diffSeconds < 60) return 'Just now';
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  if (!questions || questions.length === 0) {
    return (
      <div className="bg-white dark:bg-[#111827] border border-[#e2e8f0] dark:border-[#1f2937] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)] transition-colors duration-200">
        <div className="flex items-center space-x-2 text-slate-900 dark:text-white font-semibold text-sm mb-3">
          <div className="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 flex items-center justify-center">
            <Clock className="w-4 h-4" />
          </div>
          <span>Recent questions</span>
        </div>
        <p className="text-slate-400 dark:text-slate-500 text-xs py-3 text-center">
          Submitted questions will be preserved here for instant re-analysis.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-[#111827] border border-[#e2e8f0] dark:border-[#1f2937] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)] transition-colors duration-200">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2 text-slate-900 dark:text-white font-semibold text-sm">
          <div className="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 flex items-center justify-center">
            <Clock className="w-4 h-4" />
          </div>
          <span>Recent questions</span>
        </div>

        <button
          type="button"
          onClick={onClearAll}
          className="text-[11px] text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors flex items-center space-x-1"
          title="Clear recent history"
        >
          <Trash2 className="w-3 h-3" />
          <span>Clear</span>
        </button>
      </div>

      {/* Questions List */}
      <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
        {questions.map((item) => (
          <div
            key={item.id}
            className="group flex items-center justify-between p-2 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors cursor-pointer border border-transparent hover:border-slate-100 dark:hover:border-slate-800"
          >
            <div
              className="flex items-start space-x-2.5 flex-1 min-w-0 pr-2"
              onClick={() => onSelectQuestion(item.question, item.ticker)}
            >
              <FileText className="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-600 dark:group-hover:text-blue-400 mt-0.5 flex-shrink-0 transition-colors" />
              <div className="min-w-0 flex-1">
                <p className="text-xs text-slate-700 dark:text-slate-300 group-hover:text-slate-900 dark:group-hover:text-white font-medium truncate">
                  {item.question}
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-2 flex-shrink-0">
              <span className="text-[11px] text-slate-400 dark:text-slate-500 whitespace-nowrap">
                {formatRelativeTime(item.timestamp)}
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onRemoveQuestion(item.id);
                }}
                className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-300 hover:text-slate-500 dark:hover:text-slate-300 rounded transition-opacity"
                title="Remove entry"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
