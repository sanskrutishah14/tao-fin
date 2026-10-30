import React, { useState, useEffect } from 'react';
import { Navbar, NavigationTab } from './components/common/Navbar';
import { AskPage } from './pages/AskPage';
import { CompaniesPage } from './pages/CompaniesPage';
import { MarketPage } from './pages/MarketPage';
import { AboutPage } from './pages/AboutPage';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavigationTab>('ask');
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('taofin_dark_mode');
      if (saved !== null) {
        return saved === 'true';
      }
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      if (darkMode) {
        document.documentElement.classList.add('dark');
        localStorage.setItem('taofin_dark_mode', 'true');
      } else {
        document.documentElement.classList.remove('dark');
        localStorage.setItem('taofin_dark_mode', 'false');
      }
    } catch (e) {
      console.warn('Could not persist dark mode preference', e);
    }
  }, [darkMode]);

  const toggleDarkMode = () => {
    setDarkMode((prev) => !prev);
  };

  return (
    <div className="min-h-screen bg-[#f8fafc] dark:bg-[#0b0f19] text-[#0f172a] dark:text-[#e2e8f0] flex flex-col font-sans transition-colors duration-200">
      {/* Top Navigation Bar */}
      <Navbar
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        darkMode={darkMode}
        onToggleDarkMode={toggleDarkMode}
      />

      {/* Main Page Content */}
      <main className="flex-1 pb-16">
        {currentTab === 'ask' && <AskPage />}
        {currentTab === 'companies' && <CompaniesPage />}
        {currentTab === 'market' && <MarketPage />}
        {currentTab === 'about' && <AboutPage />}
      </main>
    </div>
  );
};

export default App;
