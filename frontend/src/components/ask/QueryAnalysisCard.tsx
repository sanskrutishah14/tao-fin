import React from 'react';
import { BarChart3 } from 'lucide-react';
import { QueryAnalysis } from '../../types/api';

interface QueryAnalysisCardProps {
  analysis?: QueryAnalysis;
}

export const QueryAnalysisCard: React.FC<QueryAnalysisCardProps> = ({ analysis }) => {
  if (!analysis) {
    return (
      <div className="bg-white dark:bg-[#111827] border border-[#e2e8f0] dark:border-[#1f2937] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)] transition-colors duration-200">
        <div className="flex items-center space-x-2 text-slate-900 dark:text-white font-semibold text-sm mb-3">
          <div className="w-6 h-6 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 flex items-center justify-center">
            <BarChart3 className="w-3.5 h-3.5" />
          </div>
          <span>Query analysis</span>
        </div>
        <p className="text-slate-400 dark:text-slate-500 text-xs py-3 text-center">
          Query structure, difficulty, and temporal anchors will appear here.
        </p>
      </div>
    );
  }

  // Format question type display
  const formatTaskType = (t: string) => {
    switch (t?.toLowerCase()) {
      case 'lookup':
        return 'Statement line';
      case 'calculation':
        return 'Calculation';
      case 'comparison':
        return 'Comparison';
      case 'explanation':
        return 'Narrative';
      default:
        return t ? t.charAt(0).toUpperCase() + t.slice(1) : 'Statement line';
    }
  };

  const difficulty = analysis.difficulty?.toLowerCase() || 'simple';
  const difficultyDisplay =
    difficulty === 'simple' ? 'Simple' : difficulty === 'moderate' ? 'Moderate' : 'Complex';

  const yearsDisplay =
    analysis.years_mentioned && analysis.years_mentioned.length > 0
      ? analysis.years_mentioned.join(', ')
      : '2024';

  return (
    <div className="bg-white dark:bg-[#111827] border border-[#e2e8f0] dark:border-[#1f2937] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)] transition-colors duration-200">
      {/* Header */}
      <div className="flex items-center space-x-2 text-slate-900 dark:text-white font-semibold text-sm mb-4">
        <div className="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 flex items-center justify-center">
          <BarChart3 className="w-4 h-4" />
        </div>
        <span>Query analysis</span>
      </div>

      {/* 3 Aligned Columns */}
      <div className="grid grid-cols-3 gap-3">
        {/* Question Type */}
        <div>
          <div className="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-1.5">Question type</div>
          <div className="inline-block px-2.5 py-1 rounded-md bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 text-xs font-medium border border-blue-100 dark:border-blue-900/60">
            {formatTaskType(analysis.task_type)}
          </div>
        </div>

        {/* Difficulty */}
        <div>
          <div className="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-1.5">Difficulty</div>
          <div
            className={`inline-block px-2.5 py-1 rounded-md text-xs font-medium border ${
              difficulty === 'simple'
                ? 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border-emerald-100 dark:border-emerald-800'
                : difficulty === 'moderate'
                ? 'bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border-amber-100 dark:border-amber-800'
                : 'bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-300 border-rose-100 dark:border-rose-800'
            }`}
          >
            {difficultyDisplay}
          </div>
        </div>

        {/* Detected Years */}
        <div>
          <div className="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-1.5">Detected years</div>
          <div className="inline-block px-2.5 py-1 rounded-md bg-purple-50 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 text-xs font-medium border border-purple-100 dark:border-purple-800">
            {yearsDisplay}
          </div>
        </div>
      </div>
    </div>
  );
};
