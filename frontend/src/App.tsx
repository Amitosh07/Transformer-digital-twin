import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { Hero } from './components/Hero';
import { Problem } from './components/Problem';
import { Solution } from './components/Solution';
import { InteractiveTwinStudio } from './components/InteractiveTwinStudio';
import { PipelineWalkthrough } from './components/PipelineWalkthrough';
import { FeaturesGrid } from './components/FeaturesGrid';
import { ImpactMetrics } from './components/ImpactMetrics';
import { Architecture } from './components/Architecture';
import { Roadmap } from './components/Roadmap';
import { PitchDeckCTA } from './components/PitchDeckCTA';
import { Footer } from './components/Footer';

export function App() {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    if (isDark) {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.remove('dark');
      root.classList.add('light');
    }
  }, [isDark]);

  const toggleTheme = () => {
    setIsDark((prev) => !prev);
  };

  return (
    <div className="min-h-screen bg-[#080B11] text-slate-100 flex flex-col relative selection:bg-amber-500/30 selection:text-amber-200">
      {/* High-tech Grid Background Pattern */}
      <div className="fixed inset-0 bg-grid-pattern opacity-40 pointer-events-none z-0" />

      {/* Top Navbar */}
      <Navbar isDark={isDark} onToggleTheme={toggleTheme} />

      {/* Main Content Sections */}
      <main className="relative z-10 flex-grow">
        {/* 1. Hero Section */}
        <Hero />

        {/* 2. The Problem */}
        <Problem />

        {/* 3. The Solution */}
        <Solution />

        {/* 4. Signature Interactive Moment: Live Diagnostic Studio */}
        <InteractiveTwinStudio />

        {/* 5. How It Works: The 6-Stage Canonical Pipeline */}
        <PipelineWalkthrough />

        {/* 6. Features Grid */}
        <FeaturesGrid />

        {/* 7. Quantified Impact & Metrics */}
        <ImpactMetrics />

        {/* 8. Microservices Architecture & Data Contract */}
        <Architecture />

        {/* 10. Production Roadmap & CPRI Integration */}
        <Roadmap />

        {/* 11. One-Command Pitch Deck CTA */}
        <PitchDeckCTA />
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
}

export default App;
