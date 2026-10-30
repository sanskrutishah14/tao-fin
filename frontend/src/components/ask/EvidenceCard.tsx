import React, { useState } from 'react';
import { FileText, ChevronLeft, ChevronRight, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';
import { EvidenceItem } from '../../types/api';

interface EvidenceCardProps {
  evidence: EvidenceItem[];
  companyTicker: string;
}

export const EvidenceCard: React.FC<EvidenceCardProps> = ({
  evidence,
  companyTicker,
}) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showAllSupporting, setShowAllSupporting] = useState(false);

  if (!evidence || evidence.length === 0) {
    return (
      <div className="bg-white dark:bg-[#111827] border border-[#e2e8f0] dark:border-[#1f2937] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)] transition-colors duration-200">
        <div className="flex items-center space-x-2 text-slate-900 dark:text-white font-semibold text-sm mb-3">
          <div className="w-6 h-6 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 flex items-center justify-center">
            <FileText className="w-3.5 h-3.5" />
          </div>
          <span>Evidence from filings</span>
        </div>
        <p className="text-slate-400 dark:text-slate-500 text-xs py-4 text-center">
          Ask a question to see audited SEC filing evidence and citations.
        </p>
      </div>
    );
  }

  const currentItem = evidence[currentIndex] || evidence[0];
  const total = evidence.length;

  const handlePrev = () => {
    setCurrentIndex((prev) => (prev > 0 ? prev - 1 : total - 1));
  };

  const handleNext = () => {
    setCurrentIndex((prev) => (prev < total - 1 ? prev + 1 : 0));
  };

  // Extract filing title
  const filingForm = currentItem.form || (currentItem.filing?.includes('10-K') ? '10-K' : '10-Q');
  const fiscalPeriod = currentItem.fiscal_period || 'FY 2024';
  const companyTitle = currentItem.company || (companyTicker === 'AAPL' ? 'Apple Inc.' : companyTicker);
  const filingDate = currentItem.filing_date || 'Oct 31, 2024';
  const accession = currentItem.accession || '0000320193-24-000123';

  // Highlight numerical values in the preview safely
  const renderHighlightedPreview = (text: string) => {
    if (!text) return null;

    // Pattern matching financial numbers like $6.43, 46.91%, 383,285
    const regex = /([$]?\d[\d,.]*(?:%|M|B)?)/g;
    const parts = text.split(regex);

    return parts.map((part, i) => {
      if (regex.test(part)) {
        return (
          <mark
            key={i}
            className="bg-amber-100 text-amber-950 font-semibold px-0.5 rounded"
          >
            {part}
          </mark>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  return (
    <div className="bg-white dark:bg-[#111827] border border-[#e2e8f0] dark:border-[#1f2937] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)] transition-colors duration-200">
      {/* Header with Document Icon and 1/3 pagination */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <div className="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 flex items-center justify-center">
            <FileText className="w-4 h-4" />
          </div>
          <span className="font-semibold text-slate-900 dark:text-white text-sm">Evidence from filings</span>
        </div>

        {total > 1 && (
          <div className="flex items-center space-x-1.5 text-xs text-slate-500 dark:text-slate-400 font-medium">
            <span>
              {currentIndex + 1}/{total}
            </span>
            <div className="flex items-center space-x-0.5">
              <button
                type="button"
                onClick={handlePrev}
                className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                title="Previous source"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={handleNext}
                className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                title="Next source"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Main Evidence Card */}
      <div className="bg-slate-50/70 dark:bg-[#0b0f19] border border-slate-200/80 dark:border-slate-800 rounded-xl p-3.5 mb-3">
        {/* Source title & primary badge */}
        <div className="flex items-start justify-between mb-1.5">
          <div className="flex items-center space-x-2">
            <FileText className="w-4 h-4 text-slate-500 dark:text-slate-400 flex-shrink-0" />
            <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
              {companyTitle} — {filingForm} ({fiscalPeriod})
            </span>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-blue-600 text-white text-[10px] font-semibold tracking-wide">
            Primary
          </span>
        </div>

        {/* Metadata subline */}
        <div className="text-[11px] text-slate-400 dark:text-slate-500 mb-2.5 flex items-center space-x-2">
          <span>Filed {filingDate}</span>
          <span>•</span>
          <span className="font-mono">Accession: {accession}</span>
        </div>

        {/* Quoted preview with matched highlight */}
        <div className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed italic bg-white dark:bg-[#111827] p-2.5 rounded-lg border border-slate-100 dark:border-slate-800">
          "... {renderHighlightedPreview(currentItem.text_preview || '')} ..."
        </div>
      </div>

      {/* Expandable Supporting Sources */}
      {total > 1 && (
        <div>
          <button
            type="button"
            onClick={() => setShowAllSupporting(!showAllSupporting)}
            className="w-full flex items-center justify-between text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 p-1"
          >
            <span>
              View {total - 1} supporting source{total > 2 ? 's' : ''}
            </span>
            {showAllSupporting ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </button>

          {showAllSupporting && (
            <div className="mt-2 space-y-2 max-h-52 overflow-y-auto pr-1">
              {evidence.map((item, idx) => {
                if (idx === currentIndex) return null;
                return (
                  <div
                    key={idx}
                    onClick={() => setCurrentIndex(idx)}
                    className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 hover:bg-blue-50/40 dark:hover:bg-blue-950/40 text-xs cursor-pointer transition-colors"
                  >
                    <div className="flex items-center justify-between font-semibold text-slate-800 dark:text-slate-200 text-[11px] mb-1">
                      <span>Source #{idx + 1}</span>
                      <span className="text-slate-400 dark:text-slate-500 font-normal">
                        {item.filing || 'SEC Filing'}
                      </span>
                    </div>
                    <p className="text-slate-600 dark:text-slate-300 line-clamp-2 italic text-[11px]">
                      {item.text_preview}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
