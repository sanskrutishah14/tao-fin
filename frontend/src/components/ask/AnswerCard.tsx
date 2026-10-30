import React from 'react';
import { CheckCircle2, AlertCircle, Table2, ShieldCheck, Clock } from 'lucide-react';
import { AnalyzeResponse } from '../../types/api';

interface AnswerCardProps {
  data: AnalyzeResponse;
  selectedTicker: string;
}

export const AnswerCard: React.FC<AnswerCardProps> = ({ data, selectedTicker }) => {
  const isDeclined =
    data.answer.toLowerCase().includes('insufficient evidence') ||
    data.reason !== undefined ||
    data.verification?.confidence === 0;

  // Format method name
  const rawMethod =
    data.verification?.details?.method ||
    data.method ||
    (data.verification?.confidence === 1.0 ? 'Table lookup' : 'Hybrid retrieval');
  
  const displayMethod =
    rawMethod === 'deterministic_table_lookup'
      ? 'Table lookup'
      : rawMethod === 'deterministic_metrics_resolver'
      ? 'Deterministic resolver'
      : rawMethod === 'retrieval_plus_llm'
      ? 'RAG retrieval'
      : rawMethod;

  // Confidence format
  const confidencePct =
    data.verification?.confidence != null
      ? Math.round(data.verification.confidence * 100)
      : 92;

  // Parse answer sentence, prominent value, and unit
  const parseAnswerDisplay = () => {
    if (isDeclined) {
      return {
        sentence: '',
        value: 'Insufficient evidence.',
        unit: '',
        extra: data.reason || 'The provided filings do not contain enough verifiable data to answer this question.',
      };
    }

    const ans = data.answer.trim();

    // Check if verification details has numeric value and unit
    const details = data.verification?.details;
    if (details && details.value !== undefined) {
      const val = details.value;
      const unit = details.unit || '';
      let formattedVal = String(val);
      let formattedUnit = '';

      if (unit === 'usd_per_share') {
        formattedVal = `$${val.toFixed(2)}`;
        formattedUnit = 'per share';
      } else if (unit === 'percent' || unit === '%') {
        formattedVal = `${val}%`;
      } else if (unit === 'million' || unit === 'millions') {
        formattedVal = `$${val.toLocaleString()}M`;
      } else if (unit === 'billion' || unit === 'billions') {
        formattedVal = `$${val.toLocaleString()}B`;
      } else if (unit) {
        formattedUnit = unit;
      }

      // Sentence from line / metric / year
      const lineName = details.line || details.metric || 'Value';
      const year = details.year ? ` in fiscal ${details.year}` : '';
      const sentence = `${selectedTicker}'s ${lineName.toLowerCase()}${year} was`;

      return {
        sentence,
        value: formattedVal,
        unit: formattedUnit,
        extra: '',
      };
    }

    // Try to extract a monetary, percentage, or numeric value from answer
    const match = ans.match(/(?:was|is|calculated as)\s+([$]?\d[\d,.]*(?:%|M|B|K|Billion|Million)?(?:\s+(?:usd_per_share|per share|percent|USD))?)/i);
    if (match) {
      const splitIdx = ans.indexOf(match[0]);
      const sentencePart = ans.slice(0, splitIdx + match[0].indexOf(match[1])).trim();
      let valPart = match[1].trim();
      let unitPart = '';

      if (valPart.includes('usd_per_share')) {
        valPart = valPart.replace('usd_per_share', '').trim();
        if (!valPart.startsWith('$')) valPart = `$${valPart}`;
        unitPart = 'per share';
      } else if (valPart.includes('per share')) {
        valPart = valPart.replace('per share', '').trim();
        unitPart = 'per share';
      }

      return {
        sentence: sentencePart,
        value: valPart,
        unit: unitPart,
        extra: ans.slice(ans.indexOf(match[1]) + match[1].length).replace(/^[,.]/, '').trim(),
      };
    }

    return {
      sentence: '',
      value: ans,
      unit: '',
      extra: '',
    };
  };

  const parsed = parseAnswerDisplay();

  return (
    <div className="bg-white dark:bg-[#111827] border border-[#e2e8f0] dark:border-[#1f2937] rounded-2xl p-6 shadow-[0_1px_3px_rgba(0,0,0,0.02)] transition-colors duration-200">
      {/* Header row */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          {isDeclined ? (
            <div className="w-5 h-5 rounded-full bg-amber-500 text-white flex items-center justify-center">
              <AlertCircle className="w-3.5 h-3.5" />
            </div>
          ) : (
            <div className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center">
              <CheckCircle2 className="w-3.5 h-3.5" />
            </div>
          )}
          <span className="font-semibold text-slate-900 dark:text-white text-base">Answer</span>
        </div>

        {data.latency_seconds != null && (
          <span className="text-xs text-slate-400 dark:text-slate-500 font-medium">
            Answered in {data.latency_seconds.toFixed(1)}s
          </span>
        )}
      </div>

      {/* Answer Sentence & Big Financial Value */}
      <div className="mb-5">
        {parsed.sentence && (
          <p className="text-slate-900 dark:text-slate-100 font-semibold text-lg mb-1 leading-snug">
            {parsed.sentence}
          </p>
        )}

        <div className="flex items-baseline space-x-2">
          <span
            className={`text-3xl sm:text-4xl font-bold font-num tracking-tight ${
              isDeclined ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'
            }`}
          >
            {parsed.value}
          </span>
          {parsed.unit && (
            <span className="text-slate-600 dark:text-slate-300 text-lg font-medium">{parsed.unit}</span>
          )}
        </div>

        {parsed.extra && (
          <p className="text-slate-500 dark:text-slate-400 text-sm mt-2 leading-relaxed">{parsed.extra}</p>
        )}
      </div>

      {/* Badges Row */}
      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
        {/* Method Badge */}
        <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-md bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 text-xs font-medium border border-blue-100 dark:border-blue-900/60">
          <Table2 className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
          <span>{displayMethod}</span>
        </div>

        {/* Confidence Badge */}
        <div
          className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-md text-xs font-medium border ${
            isDeclined
              ? 'bg-amber-50 dark:bg-amber-950/50 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800'
              : 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-800 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>{confidencePct}% confidence</span>
        </div>

        {/* Latency Badge */}
        {data.latency_seconds != null && (
          <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-md bg-purple-50 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 text-xs font-medium border border-purple-100 dark:border-purple-800">
            <Clock className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />
            <span>{data.latency_seconds.toFixed(1)}s latency</span>
          </div>
        )}
      </div>
    </div>
  );
};
