import { RecentQuestion } from '../types/api';

const STORAGE_KEY = 'taofin_recent_questions_v1';

export const storage = {
  getRecentQuestions(): RecentQuestion[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed.slice(0, 10);
      }
      return [];
    } catch (e) {
      console.warn('Failed to load recent questions from localStorage', e);
      return [];
    }
  },

  addRecentQuestion(question: string, ticker: string): RecentQuestion[] {
    try {
      const current = this.getRecentQuestions();
      // Remove any exact match to bring it to top
      const filtered = current.filter(
        (item) => item.question.toLowerCase().trim() !== question.toLowerCase().trim()
      );
      const newItem: RecentQuestion = {
        id: `${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
        question: question.trim(),
        ticker: ticker.toUpperCase().trim(),
        timestamp: Date.now(),
      };
      const updated = [newItem, ...filtered].slice(0, 10);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      return updated;
    } catch (e) {
      console.warn('Failed to save recent question to localStorage', e);
      return [];
    }
  },

  removeRecentQuestion(id: string): RecentQuestion[] {
    try {
      const current = this.getRecentQuestions();
      const updated = current.filter((item) => item.id !== id);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      return updated;
    } catch (e) {
      console.warn('Failed to remove recent question from localStorage', e);
      return [];
    }
  },

  clearRecentQuestions(): void {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      console.warn('Failed to clear recent questions', e);
    }
  },
};
