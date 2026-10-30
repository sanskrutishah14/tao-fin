import React from 'react';
import { HelpCircle } from 'lucide-react';

interface ExamplePromptsProps {
  onSelectPrompt: (question: string) => void;
  selectedTicker: string;
}

export const ExamplePrompts: React.FC<ExamplePromptsProps> = ({
  onSelectPrompt,
  selectedTicker,
}) => {
  const companyName = selectedTicker === 'AAPL' ? "Apple's" : `${selectedTicker}'s`;

  const prompts = [
    {
      label: 'Total revenue in 2024?',
      fullQuestion: `What was ${companyName} total revenue in fiscal 2024?`,
    },
    {
      label: 'Net income growth 2023 → 2024?',
      fullQuestion: `What was the net income growth rate from 2023 to 2024 for ${companyName}?`,
    },
    {
      label: 'Gross margin in 2024?',
      fullQuestion: `What was ${companyName} gross margin in fiscal 2024?`,
    },
    {
      label: 'Compare operating income 2023 vs 2024',
      fullQuestion: `Compare ${companyName} operating income in 2023 vs 2024.`,
    },
    {
      label: 'Convert revenue to billions of USD',
      fullQuestion: `Convert ${companyName} revenue in 2024 to billions of USD.`,
    },
    {
      label: 'Current stock price?',
      fullQuestion: `What is ${selectedTicker}'s current stock price?`,
    },
  ];

  return (
    <div className="bg-white dark:bg-[#111827] border border-[#e2e8f0] dark:border-[#1f2937] rounded-2xl p-6 shadow-[0_1px_3px_rgba(0,0,0,0.02)] transition-colors duration-200">
      {/* Title area */}
      <div className="flex items-start space-x-3 mb-5">
        <div className="w-9 h-9 rounded-full bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center flex-shrink-0 mt-0.5">
          <HelpCircle className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-[26px] font-semibold tracking-tight text-slate-900 dark:text-white leading-tight">
            Ask about U.S. companies
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
            Get precise answers from SEC 10-K and 10-Q filings with full traceability.
          </p>
        </div>
      </div>

      {/* 6 Example Chips */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
        {prompts.map((p, index) => (
          <button
            key={index}
            type="button"
            onClick={() => onSelectPrompt(p.fullQuestion)}
            className="flex items-center justify-center text-center p-3 text-xs font-medium text-slate-700 dark:text-slate-300 bg-slate-50/80 dark:bg-slate-800/60 hover:bg-blue-50/60 dark:hover:bg-blue-950/50 hover:text-blue-700 dark:hover:text-blue-400 border border-slate-200/80 dark:border-slate-700/80 hover:border-blue-200 dark:hover:border-blue-800 rounded-xl transition-all duration-150 leading-snug cursor-pointer group"
          >
            <span className="line-clamp-2">{p.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
