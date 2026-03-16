import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { MessageSquare, Send, Loader } from 'lucide-react';
import client from '../api/client';

function LevelBadge({ level }) {
  const colors = { ERROR: 'text-red-400', CRITICAL: 'text-red-300', WARN: 'text-yellow-400', WARNING: 'text-yellow-400', INFO: 'text-blue-400', DEBUG: 'text-gray-400' };
  return <span className={`font-bold text-xs ${colors[level] ?? 'text-gray-400'}`}>{level}</span>;
}

export default function NLQuery() {
  const [input, setInput] = useState('');

  const mutation = useMutation({
    mutationFn: (query) => client.post('/query', { query }).then((r) => r.data),
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim()) mutation.mutate(input.trim());
  };

  const EXAMPLES = [
    'Show me all errors from payment-service',
    'database connection timeout',
    'authentication failed',
    'high memory usage',
  ];

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <MessageSquare size={24} className="text-blue-400" />
          Natural Language Query
        </h1>
        <p className="text-gray-400 mt-1 text-sm">Search logs using plain English. The engine finds matching entries and provides an AI analysis.</p>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 text-sm"
          placeholder="e.g. Show errors from auth-service in the last hour..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={mutation.isPending}
        />
        <button
          type="submit"
          disabled={mutation.isPending || !input.trim()}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-5 py-3 rounded-xl text-sm font-medium transition-colors"
        >
          {mutation.isPending ? <Loader size={16} className="animate-spin" /> : <Send size={16} />}
          Search
        </button>
      </form>

      {!mutation.data && !mutation.isPending && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <p className="text-gray-500 text-sm mb-3">Try an example query:</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => setInput(ex)}
                className="bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs px-3 py-1.5 rounded-lg border border-gray-700 transition-colors"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}

      {mutation.data && (
        <div className="space-y-4">
          <div className="bg-blue-900/20 border border-blue-800/50 rounded-xl p-4">
            <p className="text-blue-300 text-sm font-medium flex items-center gap-2">
              <MessageSquare size={16} />
              AI Analysis
            </p>
            <p className="text-gray-200 mt-2 text-sm leading-relaxed">{mutation.data.analysis}</p>
          </div>

          {mutation.data.logs?.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-800">
                <span className="text-gray-400 text-sm">{mutation.data.total} matching logs</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono">
                  <thead>
                    <tr className="border-b border-gray-800 text-gray-500">
                      <th className="px-4 py-2 text-left font-medium">Time</th>
                      <th className="px-4 py-2 text-left font-medium">Level</th>
                      <th className="px-4 py-2 text-left font-medium">Service</th>
                      <th className="px-4 py-2 text-left font-medium">Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mutation.data.logs.map((log, i) => (
                      <tr key={log.id ?? i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                        <td className="px-4 py-2 text-gray-500">{new Date(log.timestamp).toLocaleString()}</td>
                        <td className="px-4 py-2"><LevelBadge level={log.level} /></td>
                        <td className="px-4 py-2 text-blue-400">{log.service}</td>
                        <td className="px-4 py-2 text-gray-300 truncate max-w-sm">{log.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {mutation.isError && (
        <div className="bg-red-900/30 border border-red-800 rounded-xl p-4 text-red-400 text-sm">
          Query failed. Make sure the API service is running.
        </div>
      )}
    </div>
  );
}
