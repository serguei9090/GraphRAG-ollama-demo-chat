import React, { useEffect, useState } from 'react';
import { isAxiosError } from 'axios';
import UploadForm from './components/UploadForm';
import api from './lib/api';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface DocumentInfo {
  name: string;
  metadata?: Record<string, string>;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api';

const streamChat = async (prompt: string, onChunk: (chunk: string) => void) => {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ prompt })
  });

  if (!response.ok || !response.body) {
    throw new Error('Unable to stream chat response');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      const finalChunk = decoder.decode();
      if (finalChunk) {
        onChunk(finalChunk);
      }
      break;
    }

    const text = decoder.decode(value, { stream: true });
    if (text) {
      onChunk(text);
    }
  }
};

const App: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState<string | null>(null);
  const [usingStub, setUsingStub] = useState<boolean | null>(null);
  const [ingestSummary, setIngestSummary] = useState<string | null>(null);

  const fetchDocuments = async () => {
    const { data } = await api.get('/chat/documents');
    setDocuments(data.documents ?? []);
    if (typeof data.using_stub === 'boolean') {
      setUsingStub(data.using_stub);
    }
  };

  useEffect(() => {
    fetchDocuments().catch(() => setDocuments([]));
  }, []);

  const handleIngest = async () => {
    setStatus('ingesting');
    setError(null);
    try {
      const { data } = await api.post('/chat/ingest');
      await fetchDocuments();
      if (typeof data?.using_stub === 'boolean') {
        setUsingStub(data.using_stub);
      }
      setIngestSummary(
        `Ingested ${data?.documents_ingested ?? 0} documents` +
          (data?.graph_name ? ` into graph '${data.graph_name}'` : ' using in-memory stub') +
          (data?.ontology_refreshed ? ' (ontology refreshed)' : '')
      );
      setStatus('ready');
    } catch (err) {
      setStatus('error');
      if (isAxiosError(err) && err.response?.data?.detail) {
        setError(`Ingestion failed: ${err.response.data.detail}`);
      } else {
        setError('Ingestion failed. Ensure documents exist in the data directories.');
      }
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!input.trim()) return;

    const userMessage: ChatMessage = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage, { role: 'assistant', content: '' }]);
    setInput('');

    try {
      setStatus('chatting');
      let assistantMessage = '';
      await streamChat(userMessage.content, (chunk) => {
        assistantMessage += chunk;
        setMessages((prev) => {
          const next = [...prev];
          const lastIndex = next.length - 1;
          if (next[lastIndex]?.role === 'assistant') {
            next[lastIndex] = { role: 'assistant', content: assistantMessage };
          }
          return next;
        });
      });
      setStatus('ready');
    } catch (err) {
      setError('Chat failed. Ensure the backend is running.');
      setStatus('error');
    }
  };

  const handleUploadSuccess = async () => {
    setStatus('uploaded');
    setIngestSummary(null);
    await fetchDocuments();
  };

  const handleUploadError = (message: string) => {
    setError(message);
  };

  return (
    <div className="flex h-full bg-background text-neutral-dark">
      <aside className="w-80 bg-neutral-dark text-surface p-6 space-y-8 shadow-lg">
        <div className="space-y-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">GraphRAG Ollama</h1>
            <p className="text-sm text-surface/60">Production-ready knowledge retrieval</p>
          </div>
          <button
            type="button"
            className="w-full rounded-lg bg-primary py-2 text-surface font-medium shadow hover:bg-primary-dark transition"
            onClick={handleIngest}
          >
            Ingest Documents
          </button>
          <UploadForm onUploadSuccess={handleUploadSuccess} onError={handleUploadError} />
        </div>
        <div className="space-y-3 rounded-lg bg-surface/10 p-4">
          <h2 className="text-lg font-medium text-surface">Status</h2>
          <p className="text-sm text-surface">{status}</p>
          <p className="text-xs text-surface/70">
            Backend mode:{' '}
            {usingStub === null ? 'unknown' : usingStub ? 'stub (fallback)' : 'GraphRAG + Ollama'}
          </p>
          {ingestSummary && <p className="text-xs text-primary">{ingestSummary}</p>}
          {error && <p className="text-sm text-red-300">{error}</p>}
        </div>
        <div className="space-y-3">
          <h2 className="text-lg font-medium text-surface">Documents</h2>
          <ul className="text-sm text-surface/80 space-y-3">
            {documents.map((doc) => (
              <li
                key={doc.name}
                className="truncate rounded-lg bg-surface/10 px-3 py-2"
                title={doc.metadata?.path ?? doc.name}
              >
                <span className="block font-medium text-surface">{doc.name}</span>
                {doc.metadata?.path && (
                  <span className="block text-xs text-surface/60">{doc.metadata.path}</span>
                )}
                {doc.metadata?.sha1 && (
                  <span className="block text-xs text-surface/50">hash: {doc.metadata.sha1}</span>
                )}
              </li>
            ))}
            {documents.length === 0 && <li className="text-xs text-surface/60">No documents ingested</li>}
          </ul>
        </div>
      </aside>
      <main className="flex-1 flex flex-col bg-background">
        <section className="flex-1 overflow-y-auto p-8 space-y-4">
          {messages.map((message, index) => (
            <div key={index} className={message.role === 'user' ? 'text-right' : 'text-left'}>
              <span
                className={`inline-block max-w-xl rounded-2xl px-4 py-3 shadow-sm ${
                  message.role === 'user'
                    ? 'bg-primary text-surface'
                    : 'bg-surface text-neutral-dark border border-primary/10'
                }`}
              >
                {message.content}
              </span>
            </div>
          ))}
          {messages.length === 0 && (
            <p className="text-muted">Send a prompt to begin chatting with the ingested knowledge base.</p>
          )}
        </section>
        <form onSubmit={handleSubmit} className="p-6 bg-surface border-t border-primary/10 flex space-x-3">
          <input
            className="flex-1 rounded-lg border border-primary/30 bg-background px-4 py-3 text-neutral-dark placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-primary"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask a question..."
          />
          <button
            type="submit"
            className="rounded-lg bg-primary px-5 py-3 text-surface font-medium shadow hover:bg-primary-dark transition"
          >
            Send
          </button>
        </form>
      </main>
    </div>
  );
};

export default App;
