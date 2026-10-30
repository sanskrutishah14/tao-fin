import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { AnalyzeResponse } from '../../types/api';

interface FormulaSourceRowProps {
  data: AnalyzeResponse;
}

export const FormulaSourceRow: React.FC<FormulaSourceRowProps> = ({ data }) => {
  const [copiedFormula, setCopiedFormula] = useState(false);
  const [copiedSource, setCopiedSource] = useState(false);

  const details = data.verification?.details;

  // Extract formula if available
  let formulaText: string | null = null;
  if (details?.formula) {
    formulaText = details.formula;
  } else if (details?.method === 'deterministic_metrics_resolver') {
    if (details.numerator && details.denominator) {
      formulaText = `${details.metric?.toUpperCase()} = ${details.numerator.label}\n${' '.repeat(
        (details.metric?.length || 6) + 3
      )}------------------------ * 100\n${' '.repeat(
        (details.metric?.length || 6) + 3
      )}${details.denominator.label}`;
    }
  } else if (details?.growth) {
    formulaText = `Growth = (End Value - Start Value) / Start Value * 100`;
  } else if (details?.line && details.line.toLowerCase().includes('diluted earnings per share')) {
    formulaText = `Diluted EPS = Net income (diluted)\n              --------------------------\n              Diluted shares outstanding`;
  }

  // Extract source row if available
  let sourceRowText: string | null = null;
  if (details?.source_line) {
    sourceRowText = details.source_line;
  } else if (data.evidence && data.evidence.length > 0) {
    // Check if first evidence has source row
    const firstEv = data.evidence[0];
    if (firstEv.text_preview) {
      sourceRowText = firstEv.text_preview;
    }
  }

  // If neither exists, do not render fabricated cards
  if (!formulaText && !sourceRowText) {
    return null;
  }

  const handleCopy = (text: string, type: 'formula' | 'source') => {
    navigator.clipboard.writeText(text);
    if (type === 'formula') {
      setCopiedFormula(true);
      setTimeout(() => setCopiedFormula(false), 2000);
    } else {
      setCopiedSource(true);
      setTimeout(() => setCopiedSource(false), 2000);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Formula Card */}
      {formulaText ? (
        <div className="bg-white dark:bg-[#111827] border border-[#e2e8f0] dark:border-[#1f2937] rounded-2xl p-4 shadow-[0_1px_3px_rgba(0,0,0,0.02)] flex flex-col justify-between transition-colors duration-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Formula <span className="font-normal text-slate-400 dark:text-slate-500">(if applicable)</span>
            </span>
            <button
              type="button"
              onClick={() => handleCopy(formulaText!, 'formula')}
              className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              title="Copy formula"
            >
              {copiedFormula ? (
                <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
          <div className="bg-[#f8fafc] dark:bg-[#0b0f19] border border-slate-200/80 dark:border-slate-800 rounded-xl p-3 text-xs font-mono text-slate-800 dark:text-slate-200 whitespace-pre overflow-x-auto leading-relaxed">
            {formulaText}
          </div>
        </div>
      ) : (
        <div className="bg-white dark:bg-[#111827] border border-[#e2e8f0] dark:border-[#1f2937] rounded-2xl p-4 shadow-[0_1px_3px_rgba(0,0,0,0.02)] flex flex-col justify-center items-center text-slate-400 text-xs py-8">
          No arithmetic formula required for direct statement lookup.
        </div>
      )}

      {/* Source Row Card */}
      {sourceRowText ? (
        <div className="bg-white dark:bg-[#111827] border border-[#e2e8f0] dark:border-[#1f2937] rounded-2xl p-4 shadow-[0_1px_3px_rgba(0,0,0,0.02)] flex flex-col justify-between transition-colors duration-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Source row <span className="font-normal text-slate-400 dark:text-slate-500">(from filing)</span>
            </span>
            <button
              type="button"
              onClick={() => handleCopy(sourceRowText!, 'source')}
              className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              title="Copy source row"
            >
              {copiedSource ? (
                <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
          <div className="bg-[#f8fafc] dark:bg-[#0b0f19] border border-slate-200/80 dark:border-slate-800 rounded-xl p-3 text-xs font-mono text-slate-800 dark:text-slate-200 whitespace-pre-wrap overflow-x-auto leading-relaxed line-clamp-4">
            {sourceRowText}
          </div>
        </div>
      ) : null}
    </div>
  );
};
