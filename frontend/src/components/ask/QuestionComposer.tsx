import React, { useState, useRef, useEffect } from 'react';
import { Send, Plus, ChevronDown, Check, Loader2 } from 'lucide-react';
import { CompanyLogo } from '../common/CompanyLogo';

interface QuestionComposerProps {
  question: string;
  onChangeQuestion: (val: string) => void;
  onSubmit: () => void;
  isLoading: boolean;
  selectedTicker: string;
  onSelectTicker: (ticker: string) => void;
  availableTickers?: string[];
}

export const QuestionComposer: React.FC<QuestionComposerProps> = ({
  question,
  onChangeQuestion,
  onSubmit,
  isLoading,
  selectedTicker,
  onSelectTicker,
  availableTickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'TSLA', 'META', 'TROW', 'VENU'],
}) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey || !e.shiftKey)) {
      e.preventDefault();
      if (!isLoading && question.trim()) {
        onSubmit();
      }
    }
  };

  return (
    <div className="sticky bottom-4 z-20 w-full mt-4">
      <div className="relative bg-white dark:bg-[#111827] border border-[#cbd5e1] dark:border-[#374151] rounded-full shadow-[0_4px_20px_rgba(0,0,0,0.08)] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)] flex items-center px-3 py-2 transition-all focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 dark:focus-within:ring-blue-900/50">
        {/* Left Plus icon */}
        <button
          type="button"
          className="w-8 h-8 rounded-full bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-500 dark:text-slate-400 flex items-center justify-center flex-shrink-0 mr-2 transition-colors"
          title="Add context or filing"
        >
          <Plus className="w-4 h-4" />
        </button>

        {/* Input Textarea */}
        <textarea
          ref={textareaRef}
          rows={1}
          value={question}
          onChange={(e) => onChangeQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about a company's 10-K or 10-Q..."
          disabled={isLoading}
          className="flex-1 bg-transparent text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none resize-none py-1.5 px-1 max-h-24 overflow-y-auto"
        />

        {/* Right Section: Ticker selector, Ctrl+Enter hint, Send button */}
        <div className="flex items-center space-x-3 ml-2 flex-shrink-0">
          {/* Company Ticker selector pill */}
          <div className="relative" ref={dropdownRef}>
            <button
              type="button"
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-xs font-semibold text-slate-800 dark:text-slate-200 transition-colors"
              title="Change selected company"
            >
              <CompanyLogo ticker={selectedTicker} size="xs" />
              <span>{selectedTicker}</span>
              <ChevronDown className="w-3 h-3 text-slate-400 ml-0.5" />
            </button>

            {/* Dropdown menu */}
            {dropdownOpen && (
              <div className="absolute right-0 bottom-full mb-2 w-44 bg-white dark:bg-[#1f2937] rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 py-1.5 z-50 animate-in fade-in slide-in-from-bottom-2 duration-150 max-h-56 overflow-y-auto">
                <div className="px-3 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Select Company
                </div>
                {availableTickers.map((ticker) => (
                  <button
                    key={ticker}
                    type="button"
                    onClick={() => {
                      onSelectTicker(ticker);
                      setDropdownOpen(false);
                    }}
                    className={`w-full flex items-center justify-between px-3 py-1.5 text-xs text-left hover:bg-slate-50 dark:hover:bg-slate-700/60 transition-colors ${
                      selectedTicker === ticker
                        ? 'text-blue-600 dark:text-blue-400 font-semibold bg-blue-50/50 dark:bg-blue-900/30'
                        : 'text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    <div className="flex items-center space-x-2">
                      <CompanyLogo ticker={ticker} size="xs" />
                      <span>{ticker}</span>
                    </div>
                    {selectedTicker === ticker && <Check className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Keyboard shortcut hint */}
          <span className="hidden sm:inline-block text-[11px] font-medium text-slate-400 select-none">
            Ctrl + Enter
          </span>

          {/* Round blue send button */}
          <button
            type="button"
            onClick={onSubmit}
            disabled={isLoading || !question.trim()}
            className={`w-9 h-9 rounded-full flex items-center justify-center transition-all duration-150 ${
              isLoading || !question.trim()
                ? 'bg-blue-400 dark:bg-blue-600/50 text-white/70 cursor-not-allowed opacity-80'
                : 'bg-blue-600 hover:bg-blue-700 active:scale-95 text-white shadow-sm'
            }`}
            title="Submit question"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4 ml-0.5" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
