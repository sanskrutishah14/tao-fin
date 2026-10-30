import React, { useState, useEffect } from 'react';
import { ExamplePrompts } from '../components/ask/ExamplePrompts';
import { AnswerCard } from '../components/ask/AnswerCard';
import { FormulaSourceRow } from '../components/ask/FormulaSourceRow';
import { VerificationBanner } from '../components/ask/VerificationBanner';
import { TaoTrace } from '../components/ask/TaoTrace';
import { QuestionComposer } from '../components/ask/QuestionComposer';
import { EvidenceCard } from '../components/ask/EvidenceCard';
import { QueryAnalysisCard } from '../components/ask/QueryAnalysisCard';
import { MarketSnapshotCard } from '../components/ask/MarketSnapshotCard';
import { RecentQuestionsCard } from '../components/ask/RecentQuestionsCard';
import { AnalyzeResponse, RecentQuestion } from '../types/api';
import { api } from '../services/api';
import { storage } from '../services/storage';
import { AlertCircle, X } from 'lucide-react';

interface AskPageProps {
  initialTicker?: string;
  onNavigateToCompanies?: () => void;
}

export const AskPage: React.FC<AskPageProps> = ({ initialTicker = 'AAPL' }) => {
  const [question, setQuestion] = useState('');
  const [selectedTicker, setSelectedTicker] = useState(initialTicker);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // QA Result State
  const [response, setResponse] = useState<AnalyzeResponse | null>(null);

  // Recent questions
  const [recentQuestions, setRecentQuestions] = useState<RecentQuestion[]>([]);

  // Available tickers
  const [availableTickers, setAvailableTickers] = useState<string[]>([
    'AAPL',
    'MSFT',
    'NVDA',
    'GOOGL',
    'AMZN',
    'TSLA',
    'META',
    'TROW',
    'VENU',
  ]);

  useEffect(() => {
    // Load recent questions from storage
    setRecentQuestions(storage.getRecentQuestions());

    // Fetch synced companies from API to populate ticker dropdown
    api
      .getCompanies()
      .then((res) => {
        if (res?.companies && res.companies.length > 0) {
          const tickers = Array.from(
            new Set([
              ...res.companies.map((c) => c.ticker),
              'AAPL',
              'MSFT',
              'NVDA',
              'GOOGL',
              'AMZN',
              'TSLA',
            ])
          );
          setAvailableTickers(tickers);
        }
      })
      .catch(() => {});
  }, []);

  const handleSelectPrompt = (promptQuestion: string) => {
    setQuestion(promptQuestion);
  };

  const executeQuery = async (queryText: string, tickerToUse: string) => {
    const q = queryText.trim();
    if (!q) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await api.analyze(q, tickerToUse);
      setResponse(data);

      // Save to recent questions on success
      const updated = storage.addRecentQuestion(q, tickerToUse);
      setRecentQuestions(updated);
    } catch (err: any) {
      console.error('Failed to analyze question:', err);
      setError(err?.message || 'Failed to submit question to TAO-Fin. Please verify backend is running.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = () => {
    if (!question.trim() || isLoading) return;
    executeQuery(question, selectedTicker);
  };

  const handleRerunRecent = (recentQ: string, recentTicker: string) => {
    setQuestion(recentQ);
    setSelectedTicker(recentTicker);
    executeQuery(recentQ, recentTicker);
  };

  const handleRemoveRecent = (id: string) => {
    const updated = storage.removeRecentQuestion(id);
    setRecentQuestions(updated);
  };

  const handleClearRecent = () => {
    storage.clearRecentQuestions();
    setRecentQuestions([]);
  };

  const isDeclined =
    response?.answer.toLowerCase().includes('insufficient evidence') ||
    response?.reason !== undefined ||
    response?.verification?.confidence === 0;

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Error banner if query fails */}
      {error && (
        <div className="mb-4 p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 flex items-center justify-between text-sm animate-in fade-in">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-rose-500 hover:text-rose-700 p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Two-column layout: 64% Left, 36% Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (~64%, 8 of 12 cols in lg grid) */}
        <div className="lg:col-span-8 flex flex-col space-y-5">
          {/* 1. Question Area & 6 Example Chips */}
          <ExamplePrompts
            onSelectPrompt={handleSelectPrompt}
            selectedTicker={selectedTicker}
          />

          {/* 2. Answer Card (when available) */}
          {response && (
            <>
              <AnswerCard data={response} selectedTicker={selectedTicker} />

              {/* 3. Formula & Source Row Cards */}
              <FormulaSourceRow data={response} />

              {/* 4. Compact Verification Banner */}
              <VerificationBanner
                verification={response.verification}
                isDeclined={isDeclined}
              />

              {/* 5. Collapsible TAO Trace */}
              {response.tao && <TaoTrace trace={response.tao} />}
            </>
          )}

          {/* 6. Floating Question Composer */}
          <QuestionComposer
            question={question}
            onChangeQuestion={setQuestion}
            onSubmit={handleSubmit}
            isLoading={isLoading}
            selectedTicker={selectedTicker}
            onSelectTicker={setSelectedTicker}
            availableTickers={availableTickers}
          />
        </div>

        {/* Right Column (~36%, 4 of 12 cols in lg grid) */}
        <div className="lg:col-span-4 flex flex-col space-y-5">
          {/* 1. Evidence from filings */}
          <EvidenceCard
            evidence={response?.evidence || []}
            companyTicker={selectedTicker}
          />

          {/* 2. Query analysis */}
          <QueryAnalysisCard analysis={response?.query_analysis} />

          {/* 3. Market snapshot */}
          <MarketSnapshotCard
            ticker={selectedTicker}
            snapshot={response?.market_snapshot}
          />

          {/* 4. Recent questions */}
          <RecentQuestionsCard
            questions={recentQuestions}
            onSelectQuestion={handleRerunRecent}
            onRemoveQuestion={handleRemoveRecent}
            onClearAll={handleClearRecent}
          />
        </div>
      </div>
    </div>
  );
};
