import React, { useEffect, useState } from 'react';
import axios from 'axios';
import UploadForm from './components/UploadForm';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

const streamChat = async (prompt: string, onChunk: (chunk: string) => void) => {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ prompt })
  });

  if (!response.body) {
    throw new Error('No response body');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let chunk = await reader.read();
  while (!chunk.done) {
    onChunk(decoder.decode(chunk.value));
    chunk = await reader.read();
  }
};

const App: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [documents, setDocuments] = useState<string[]>([]);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState<string | null>(null);

  const fetchDocuments = async () => {
    const { data } = await axios.get('/api/chat/documents');
    setDocuments(data.documents);
  };

  useEffect(() => {
    fetchDocuments().catch(() => setDocuments([]));
  }, []);

  const handleIngest = async () => {
    setStatus('ingesting');
    setError(null);
    try {
      await axios.post('/api/chat/ingest');
      await fetchDocuments();
      setStatus('ready');
    } catch (err) {
      setStatus('error');
      setError('Ingestion failed. Ensure documents exist in the data directories.');
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!input.trim()) return;

    const userMessage: ChatMessage = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');

    try {
      let assistantMessage = '';
      await streamChat(userMessage.content, (chunk) => {
        assistantMessage += chunk;
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last && last.role === 'assistant' && last.content === assistantMessage.slice(0, -chunk.length)) {
            next[next.length - 1] = { role: 'assistant', content: assistantMessage };
          } else {
            next.push({ role: 'assistant', content: assistantMessage });
          }
          return next;
        });
      });
    } catch (err) {
      setError('Chat failed. Ensure the backend is running.');
    }
  };

  const handleUploadSuccess = async () => {
    setStatus('uploaded');
    await fetchDocuments();
  };

  const handleUploadError = (message: string) => {
    setError(message);
  };

  return (
    <div className="flex h-full">
      <aside className="w-72 bg-slate-800 p-4 space-y-6">
        <div className="space-y-4">
          <h1 className="text-xl font-semibold">GraphRAG Ollama</h1>
          <button
            type="button"
            className="w-full rounded bg-emerald-500 py-2 text-white hover:bg-emerald-400"
            onClick={handleIngest}
          >
            Ingest Documents
          </button>
          <UploadForm onUploadSuccess={handleUploadSuccess} onError={handleUploadError} />
        </div>
        <div>
          <h2 className="text-lg font-medium">Status</h2>
          <p className="text-sm text-slate-300">{status}</p>
          {error && <p className="text-sm text-red-400">{error}</p>}
        </div>
        <div>
          <h2 className="text-lg font-medium">Documents</h2>
          <ul className="text-sm text-slate-300 space-y-1">
            {documents.map((doc) => (
              <li key={doc} className="truncate" title={doc}>
                {doc}
              </li>
            ))}
            {documents.length === 0 && <li>No documents ingested</li>}
          </ul>
        </div>
      </aside>
      <main className="flex-1 flex flex-col">
        <section className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((message, index) => (
            <div key={index} className={message.role === 'user' ? 'text-right' : 'text-left'}>
              <span
                className={`inline-block max-w-xl rounded px-3 py-2 ${
                  message.role === 'user' ? 'bg-emerald-600 text-white' : 'bg-slate-700 text-slate-100'
                }`}
              >
                {message.content}
              </span>
            </div>
          ))}
          {messages.length === 0 && (
            <p className="text-slate-400">Send a prompt to begin chatting with the ingested knowledge base.</p>
          )}
        </section>
        <form onSubmit={handleSubmit} className="p-4 bg-slate-800 flex space-x-2">
          <input
            className="flex-1 rounded bg-slate-700 px-3 py-2 text-white focus:outline-none focus:ring focus:ring-emerald-500"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask a question..."
          />
          <button
            type="submit"
            className="rounded bg-emerald-500 px-4 py-2 text-white hover:bg-emerald-400"
          >
            Send
          </button>
        </form>
      </main>
    </div>
  );
};

export default App;
