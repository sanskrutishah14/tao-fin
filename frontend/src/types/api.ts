export interface CompanySummary {
  ticker: string;
  cik: string | null;
  name: string | null;
  sector: string | null;
  industry: string | null;
  currency: string | null;
  last_synced_at: string | null;
  num_filings: number;
  has_quote: boolean;
}

export interface SECFilingItem {
  form: string;
  filing_date: string;
  report_date: string | null;
  filing_url: string;
  indexed: boolean;
  accession_number?: string;
}

export interface MarketQuote {
  symbol: string;
  exchange: string;
  last_price: number | null;
  previous_close: number | null;
  change: number | null;
  change_pct: number | null;
  day_high?: number | null;
  day_low?: number | null;
  volume?: number | null;
  market_cap?: number | null;
  currency?: string | null;
  fetched_at?: string;
}

export interface CompanyDetail extends CompanySummary {
  filings: SECFilingItem[];
  quote: MarketQuote | null;
}

export interface MarketHistoryPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface MarketHistoryResponse {
  symbol: string;
  exchange: string;
  period: string;
  points: MarketHistoryPoint[];
}

export interface MarketStreamStatus {
  connected: boolean;
  endpoint: string;
  subscribed: string[];
  has_latest_trade: Record<string, boolean>;
  stale_after_seconds: number;
  note?: string;
}

export interface EvidenceItem {
  score?: number;
  source?: string;
  filing?: string;
  text_preview?: string;
  page?: number | null;
  accession?: string;
  form?: string;
  company?: string;
  fiscal_period?: string;
  filing_date?: string;
}

export interface VerificationDetails {
  method?: string;
  metric?: string;
  year?: number | string;
  numerator?: { label: string; value: number };
  denominator?: { label: string; value: number };
  formula?: string;
  source_line?: string;
  line?: string;
  value?: number;
  unit?: string;
  growth?: any;
  change?: any;
}

export interface Verification {
  checks: {
    numerical?: boolean;
    evidence?: boolean;
    logical?: boolean;
    financial_consistency?: boolean;
  };
  confidence: number;
  failed_checks: string[];
  details?: VerificationDetails;
}

export interface QueryAnalysis {
  difficulty: 'simple' | 'moderate' | 'complex' | string;
  task_type: 'lookup' | 'calculation' | 'comparison' | 'explanation' | string;
  requires_calculation: boolean;
  years_mentioned: string[];
  top_k?: number;
  max_reasoning_iterations?: number;
  max_retrieval_expansions?: number;
}

export interface TAOTrace {
  reasoning_iterations?: number;
  retrieval_expansions?: number;
  verification_calls?: number;
  compute_saved_pct?: number;
  controller_action?: string;
  decisions?: string[];
}

export interface MarketSnapshot {
  symbol: string;
  price: number | null;
  volume?: number | null;
  timestamp?: number | null;
  received_at?: string | null;
  age_seconds?: number | null;
  is_stale?: boolean;
  source: string;
  change?: number | null;
  change_pct?: number | null;
}

export interface AnalyzeResponse {
  answer: string;
  evidence: EvidenceItem[];
  verification: Verification;
  query_analysis?: QueryAnalysis;
  tao?: TAOTrace;
  market_snapshot?: MarketSnapshot | null;
  latency_seconds?: number;
  reason?: string;
  method?: string;
}

export interface EvaluationItem {
  id: string;
  question: string;
  expected_path?: string;
  category?: string;
  availability?: string;
  ran: boolean;
  predicted_answer: string;
  gold_answer?: string;
  abstained: boolean;
  answer_correct: boolean;
  verifier_confidence?: number;
  latency_seconds?: number;
}

export interface EvaluationSummary {
  label: string;
  status: 'complete' | 'not_run' | 'blocked' | string;
  expected_total?: number;
  total?: number;
  correct?: number;
  abstained?: number;
  incorrect?: number;
  accuracy?: number;
  median_latency?: number;
  items: EvaluationItem[];
  reasons?: Array<{ id: string; reason: string }>;
}

export interface RecentQuestion {
  id: string;
  question: string;
  ticker: string;
  timestamp: number;
}
