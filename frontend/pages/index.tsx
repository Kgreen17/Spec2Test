import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [link, setLink] = useState('');
  const [inputMode, setInputMode] = useState<'file' | 'link'>('file');
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  // Fetch jobs on component mount and periodically
  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, []);

  const fetchJobs = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/jobs');
      setJobs(response.data || []);
      setError('');
    } catch (err: any) {
      console.error('Error fetching jobs:', err);
      setError('Failed to fetch jobs. Is the backend running?');
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (inputMode === 'file' && !file) {
      setError('Please select a file');
      return;
    }

    if (inputMode === 'link' && !link.trim()) {
      setError('Please enter a Confluence or Jira link');
      return;
    }

    setUploading(true);
    setError('');
    setMessage('');

    try {
      let response;

      if (inputMode === 'file') {
        const formData = new FormData();
        formData.append('file', file!);

        response = await axios.post(
          'http://localhost:8000/api/upload',
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
          }
        );
      } else {
        // Link mode
        response = await axios.post(
          'http://localhost:8000/api/upload',
          { url: link },
          {
            headers: {
              'Content-Type': 'application/json',
            },
          }
        );
      }

      setMessage(
        response.data.message ||
          (inputMode === 'file'
            ? 'File uploaded successfully! Pipeline started.'
            : 'Link submitted successfully! Pipeline started.')
      );

      if (inputMode === 'file') {
        setFile(null);
        if ((document.getElementById('fileInput') as HTMLInputElement)) {
          (document.getElementById('fileInput') as HTMLInputElement).value = '';
        }
      } else {
        setLink('');
      }

      fetchJobs();
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          'Submission failed. Check the backend and try again.'
      );
    } finally {
      setUploading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      case 'running':
        return 'bg-blue-100 text-blue-800';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h1 className="text-3xl font-bold text-gray-900">
            Spec2Test AI
          </h1>
          <p className="text-gray-600 mt-1">
            Convert specifications to automated tests using AI
          </p>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Upload Section */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-lg p-8">
              <h2 className="text-2xl font-bold text-gray-900 mb-6">
                Add Specifications
              </h2>

              {/* Mode Toggle */}
              <div className="flex gap-2 mb-6 border border-gray-200 rounded-lg p-1">
                <button
                  type="button"
                  onClick={() => {
                    setInputMode('file');
                    setError('');
                    setMessage('');
                  }}
                  className={`flex-1 py-2 px-3 rounded text-sm font-medium transition ${
                    inputMode === 'file'
                      ? 'bg-blue-600 text-white'
                      : 'bg-transparent text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  📤 Upload Document
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setInputMode('link');
                    setError('');
                    setMessage('');
                  }}
                  className={`flex-1 py-2 px-3 rounded text-sm font-medium transition ${
                    inputMode === 'link'
                      ? 'bg-blue-600 text-white'
                      : 'bg-transparent text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  🔗 Paste Link
                </button>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                {inputMode === 'file' ? (
                  // File Upload Section
                  <>
                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-500 transition">
                      <input
                        type="file"
                        id="fileInput"
                        onChange={handleFileChange}
                        disabled={uploading}
                        className="hidden"
                        accept=".pdf,.docx,.txt,.md,.xlsx,.csv"
                      />
                      <label
                        htmlFor="fileInput"
                        className="cursor-pointer block"
                      >
                        <svg
                          className="mx-auto h-12 w-12 text-gray-400 mb-3"
                          stroke="currentColor"
                          fill="none"
                          viewBox="0 0 48 48"
                        >
                          <path
                            d="M28 8H12a4 4 0 00-4 4v24a4 4 0 004 4h24a4 4 0 004-4V20m-8-12v12m0 0l-4-4m4 4l4-4"
                            strokeWidth={2}
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                        <p className="text-sm text-gray-600">
                          {file ? (
                            <span className="font-semibold text-blue-600">
                              {file.name}
                            </span>
                          ) : (
                            <>
                              <span className="font-semibold text-blue-600">
                                Click to upload
                              </span>{' '}
                              or drag and drop
                            </>
                          )}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          PDF, DOCX, TXT, MD, XLSX, CSV
                        </p>
                      </label>
                    </div>
                  </>
                ) : (
                  // Link Input Section
                  <>
                    <div className="space-y-3">
                      <label className="block text-sm font-medium text-gray-700">
                        Confluence or Jira Link
                      </label>
                      <input
                        type="url"
                        value={link}
                        onChange={(e) => setLink(e.target.value)}
                        disabled={uploading}
                        placeholder="https://your-domain.atlassian.net/wiki/spaces/... or https://your-domain.atlassian.net/browse/..."
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
                      />
                      <p className="text-xs text-gray-500">
                        Paste the full URL to a Confluence page or Jira ticket
                      </p>
                    </div>
                  </>
                )}

                <button
                  type="submit"
                  disabled={uploading || (inputMode === 'file' ? !file : !link.trim())}
                  className="w-full bg-blue-600 text-white font-semibold py-3 px-4 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition"
                >
                  {uploading
                    ? 'Processing...'
                    : (inputMode === 'file' ? 'Upload & Start Pipeline' : 'Submit & Start Pipeline')}
                </button>
              </form>

              {message && (
                <div className="mt-4 p-4 bg-green-50 border border-green-200 text-green-700 rounded-lg text-sm">
                  ✓ {message}
                </div>
              )}

              {error && (
                <div className="mt-4 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                  ✕ {error}
                </div>
              )}
            </div>
          </div>

          {/* Jobs / Status Section */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow-lg p-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">
                  Pipeline Jobs
                </h2>
                <button
                  onClick={fetchJobs}
                  className="text-blue-600 hover:text-blue-700 text-sm font-semibold"
                >
                  ↻ Refresh
                </button>
              </div>

              {jobs.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <p>No jobs yet. Upload a document to get started!</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {jobs.map((job: any) => (
                    <div
                      key={job.id || job.job_id}
                      className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <h3 className="font-semibold text-gray-900">
                            {job.filename || job.name || 'Untitled'}
                          </h3>
                          <p className="text-xs text-gray-500 mt-1">
                            ID: {job.id || job.job_id}
                          </p>
                        </div>
                        <span
                          className={`px-3 py-1 rounded-full text-sm font-medium whitespace-nowrap ml-4 ${getStatusColor(
                            job.status
                          )}`}
                        >
                          {job.status || 'unknown'}
                        </span>
                      </div>

                      <div className="mt-3 space-y-1 text-xs text-gray-600">
                        {job.created_at && (
                          <p>
                            Created:{' '}
                            {new Date(job.created_at).toLocaleString()}
                          </p>
                        )}
                        {job.updated_at && (
                          <p>
                            Updated:{' '}
                            {new Date(job.updated_at).toLocaleString()}
                          </p>
                        )}
                        {job.result && (
                          <div className="mt-2 p-2 bg-gray-50 rounded">
                            <p className="font-semibold">Result:</p>
                            <pre className="text-xs overflow-auto max-h-40 mt-1">
                              {typeof job.result === 'string'
                                ? job.result
                                : JSON.stringify(job.result, null, 2)}
                            </pre>
                          </div>
                        )}
                        {job.error && (
                          <div className="mt-2 p-2 bg-red-50 rounded text-red-700">
                            <p className="font-semibold">Error:</p>
                            <p className="text-xs mt-1">{job.error}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Info Section */}
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="font-bold text-gray-900 mb-2">📤 Upload or Link</h3>
            <p className="text-sm text-gray-600">
              Upload documents (PDF, Word, Excel, etc.) or paste a Confluence/Jira link
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="font-bold text-gray-900 mb-2">🤖 Process</h3>
            <p className="text-sm text-gray-600">
              AI analyzes content and generates test scenarios
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="font-bold text-gray-900 mb-2">✓ Tests</h3>
            <p className="text-sm text-gray-600">
              Download automated test scripts (Playwright)
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}

