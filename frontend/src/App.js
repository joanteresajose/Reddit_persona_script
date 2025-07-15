import React, { useState, useEffect } from "react";
import "./App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const App = () => {
  const [redditUrl, setRedditUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [personas, setPersonas] = useState([]);

  // Load existing personas on component mount
  useEffect(() => {
    loadPersonas();
  }, []);

  const loadPersonas = async () => {
    try {
      const response = await axios.get(`${API}/personas`);
      setPersonas(response.data);
    } catch (e) {
      console.error("Error loading personas:", e);
    }
  };

  const handleAnalyze = async () => {
    if (!redditUrl.trim()) {
      setError("Please enter a Reddit profile URL");
      return;
    }

    if (!redditUrl.includes("reddit.com/user/")) {
      setError("Please enter a valid Reddit user profile URL (e.g., https://www.reddit.com/user/username/)");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await axios.post(`${API}/analyze-reddit`, {
        reddit_url: redditUrl
      });

      setResult(response.data);
      await loadPersonas(); // Refresh personas list
    } catch (e) {
      setError(e.response?.data?.detail || "Error analyzing Reddit profile");
      console.error("Error:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (personaId) => {
    try {
      const response = await axios.get(`${API}/download-persona/${personaId}`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `persona_${personaId}.txt`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Error downloading file:", e);
    }
  };

  const renderPersonaSection = (title, data) => {
    if (!data || typeof data !== 'object') return null;
    
    return (
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-2">{title}</h3>
        <div className="bg-gray-50 p-4 rounded-lg">
          {Object.entries(data).map(([key, value]) => (
            <div key={key} className="mb-2">
              <span className="font-medium text-gray-700">{key}:</span>
              <span className="ml-2 text-gray-600">{typeof value === 'string' ? value : JSON.stringify(value)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-800 mb-4">
            Reddit User Persona Extractor
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Analyze any Reddit user's profile to create detailed personas based on their posts and comments
          </p>
        </div>

        {/* Input Section */}
        <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
          <div className="max-w-2xl mx-auto">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Reddit Profile URL
            </label>
            <div className="flex gap-4">
              <input
                type="url"
                value={redditUrl}
                onChange={(e) => setRedditUrl(e.target.value)}
                placeholder="https://www.reddit.com/user/username/"
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={loading}
              />
              <button
                onClick={handleAnalyze}
                disabled={loading}
                className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
              >
                {loading ? "Analyzing..." : "Analyze"}
              </button>
            </div>
            
            {/* Example URLs */}
            <div className="mt-4 text-sm text-gray-500">
              <p>Examples:</p>
              <ul className="list-disc list-inside mt-1 space-y-1">
                <li>https://www.reddit.com/user/kojied/</li>
                <li>https://www.reddit.com/user/Hungry-Move-6603/</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg mb-8">
            {error}
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
            <div className="flex items-center justify-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <span className="ml-4 text-lg text-gray-600">
                Analyzing Reddit profile... This may take a moment.
              </span>
            </div>
          </div>
        )}

        {/* Result Section */}
        {result && (
          <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-gray-800">
                Persona Analysis for u/{result.username}
              </h2>
              <button
                onClick={() => handleDownload(result.id)}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              >
                Download Report
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {result.persona && Object.entries(result.persona).map(([key, value]) => (
                <div key={key}>
                  {renderPersonaSection(
                    key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                    value
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Previous Analyses */}
        {personas.length > 0 && (
          <div className="bg-white rounded-lg shadow-lg p-8">
            <h2 className="text-2xl font-bold text-gray-800 mb-6">
              Previous Analyses
            </h2>
            <div className="space-y-4">
              {personas.map((persona) => (
                <div key={persona.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h3 className="font-semibold text-gray-800">u/{persona.username}</h3>
                    <p className="text-sm text-gray-600">
                      Analyzed: {new Date(persona.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDownload(persona.id)}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Download
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default App;