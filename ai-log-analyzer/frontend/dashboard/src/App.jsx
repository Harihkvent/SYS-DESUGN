import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import LogExplorer from './pages/LogExplorer';
import Anomalies from './pages/Anomalies';
import NLQuery from './pages/NLQuery';

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex flex-col min-h-screen bg-gray-950">
        <Navbar />
        <main className="flex-1 container mx-auto px-4 py-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/logs" element={<LogExplorer />} />
            <Route path="/anomalies" element={<Anomalies />} />
            <Route path="/query" element={<NLQuery />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
