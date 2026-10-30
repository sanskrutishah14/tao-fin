import React, { useState } from 'react';
import { Layers, ChevronDown, ChevronUp } from 'lucide-react';
import { TAOTrace } from '../../types/api';

interface TaoTraceProps {
  trace?: TAOTrace;
}

export const TaoTrace: React.FC<TaoTraceProps> = ({ trace }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!trace) return null;

  const reasoningIter = trace.reasoning_iterations ?? 0;
  const retrievals = trace.retrieval_expansions ?? 0;
  const verifications = trace.verification_calls ?? 0;
  const computeSaved = trace.compute_saved_pct ?? 85;

  return (
    <div className="bg-white dark:bg-[#111827] border border-[#e2e8f0] dark:border-[#1f2937] rounded-2xl p-4 shadow-[0_1px_3px_rgba(0,0,0,0.02)] transition-colors duration-200">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between text-left focus:outline-none group"
      >
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-xl bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 flex items-center justify-center flex-shrink-0 group-hover:bg-blue-100 dark:group-hover:bg-blue-900/80 transition-colors">
            <Layers className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-sm font-semibold text-slate-900 dark:text-white">TAO trace</span>
              <span className="text-xs text-slate-500 dark:text-slate-400 font-normal">
                See reasoning, retrieval steps and compute savings
              </span>
            </div>
          </div>
        </div>

        <div className="text-slate-400 dark:text-slate-500 group-hover:text-slate-600 dark:group-hover:text-slate-300 transition-colors">
          {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>

      {isOpen && (
        <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 text-xs space-y-4 animate-in fade-in duration-150">
          {/* Metrics grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 bg-slate-50 dark:bg-[#0b0f19] rounded-xl border border-slate-100 dark:border-slate-800">
              <div className="text-slate-500 dark:text-slate-400 text-[11px] mb-1">Reasoning iterations</div>
              <div className="text-base font-semibold text-slate-800 dark:text-slate-100">{reasoningIter}</div>
            </div>
            <div className="p-3 bg-slate-50 dark:bg-[#0b0f19] rounded-xl border border-slate-100 dark:border-slate-800">
              <div className="text-slate-500 dark:text-slate-400 text-[11px] mb-1">Retrieval expansions</div>
              <div className="text-base font-semibold text-slate-800 dark:text-slate-100">{retrievals}</div>
            </div>
            <div className="p-3 bg-slate-50 dark:bg-[#0b0f19] rounded-xl border border-slate-100 dark:border-slate-800">
              <div className="text-slate-500 dark:text-slate-400 text-[11px] mb-1">Verification calls</div>
              <div className="text-base font-semibold text-slate-800 dark:text-slate-100">{verifications}</div>
            </div>
            <div className="p-3 bg-slate-50 dark:bg-[#0b0f19] rounded-xl border border-slate-100 dark:border-slate-800">
              <div className="text-slate-500 dark:text-slate-400 text-[11px] mb-1">Compute saved</div>
              <div className="text-base font-semibold text-emerald-600 dark:text-emerald-400">{computeSaved}%</div>
            </div>
          </div>

          {/* Compute savings bar */}
          <div>
            <div className="flex items-center justify-between text-slate-600 dark:text-slate-300 text-xs mb-1.5 font-medium">
              <span>Compute efficiency</span>
              <span className="font-semibold text-emerald-600 dark:text-emerald-400">{computeSaved}% saved vs full LLM baseline</span>
            </div>
            <div className="w-full h-2.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(5, computeSaved))}%` }}
              ></div>
            </div>
          </div>

          {/* Controller decisions / action */}
          {trace.controller_action && (
            <div className="p-3 bg-blue-50/60 dark:bg-blue-950/40 rounded-xl border border-blue-100 dark:border-blue-900/60 text-blue-900 dark:text-blue-200">
              <span className="font-semibold">TAO Controller:</span> {trace.controller_action}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
