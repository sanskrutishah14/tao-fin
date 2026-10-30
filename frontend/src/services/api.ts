import {
  AnalyzeResponse,
  CompanyDetail,
  CompanySummary,
  EvaluationSummary,
  MarketHistoryResponse,
  MarketQuote,
  MarketStreamStatus,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function fetchJson<T>(endpoint: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  });

  const contentType = response.headers.get('content-type');
  const isJson = contentType && contentType.includes('application/json');
  const body = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const errorMsg =
      typeof body === 'object' && body !== null && 'detail' in body
        ? String(body.detail)
        : typeof body === 'string' && body.trim()
        ? body
        : response.statusText || `HTTP Error ${response.status}`;
    throw new Error(errorMsg);
  }

  return body as T;
}

export const api = {
  async analyze(question: string, ticker?: string): Promise<AnalyzeResponse> {
    return fetchJson<AnalyzeResponse>('/api/analyze', {
      method: 'POST',
      body: JSON.stringify({ question, ticker: ticker || undefined }),
    });
  },

  async getCompanies(): Promise<{ companies: CompanySummary[] }> {
    return fetchJson<{ companies: CompanySummary[] }>('/api/companies');
  },

  async getCompany(ticker: string): Promise<CompanyDetail> {
    return fetchJson<CompanyDetail>(`/api/companies/${encodeURIComponent(ticker.toUpperCase())}`);
  },

  async syncCompany(ticker: string): Promise<{ company: CompanySummary; filings_synced: number }> {
    return fetchJson<{ company: CompanySummary; filings_synced: number }>(
      `/api/companies/${encodeURIComponent(ticker.toUpperCase())}/sync`,
      { method: 'POST' }
    );
  },

  async getMarketQuote(symbol: string, exchange: string = 'US'): Promise<MarketQuote> {
    return fetchJson<MarketQuote>(
      `/api/market/quote/${encodeURIComponent(symbol.toUpperCase())}?exchange=${encodeURIComponent(exchange)}`
    );
  },

  async getMarketHistory(
    symbol: string,
    period: string = '1mo',
    exchange: string = 'US'
  ): Promise<MarketHistoryResponse> {
    return fetchJson<MarketHistoryResponse>(
      `/api/market/history/${encodeURIComponent(symbol.toUpperCase())}?period=${encodeURIComponent(
        period
      )}&exchange=${encodeURIComponent(exchange)}`
    );
  },

  async getMarketStreamStatus(): Promise<MarketStreamStatus> {
    return fetchJson<MarketStreamStatus>('/api/market/stream/status');
  },

  async getMarketStreamLatest(symbol: string): Promise<any> {
    return fetchJson<any>(`/api/market/stream/${encodeURIComponent(symbol.toUpperCase())}`);
  },

  async subscribeMarketStream(symbol: string): Promise<any> {
    return fetchJson<any>('/api/market/stream/subscribe', {
      method: 'POST',
      body: JSON.stringify({ symbol: symbol.toUpperCase() }),
    });
  },

  async unsubscribeMarketStream(symbol: string): Promise<any> {
    return fetchJson<any>('/api/market/stream/unsubscribe', {
      method: 'POST',
      body: JSON.stringify({ symbol: symbol.toUpperCase() }),
    });
  },

  async getEvaluation(run: string): Promise<EvaluationSummary> {
    return fetchJson<EvaluationSummary>(`/api/eval/${encodeURIComponent(run)}`);
  },

  async getEvaluationRuns(): Promise<{ runs: Array<{ id: string; label: string; count: number }> }> {
    try {
      return await fetchJson<{ runs: Array<{ id: string; label: string; count: number }> }>('/api/eval/runs');
    } catch {
      return {
        runs: [
          { id: 'smoke', label: 'Smoke (8)', count: 8 },
          { id: 'validation', label: 'Validation (12)', count: 12 },
          { id: 'dev', label: 'Dev Run (50)', count: 50 },
        ],
      };
    }
  },
};
