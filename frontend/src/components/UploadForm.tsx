import React, { useState } from 'react';
import api from '../lib/api';

interface UploadFormProps {
  onUploadSuccess: () => void;
  onError: (message: string) => void;
}

const UploadForm: React.FC<UploadFormProps> = ({ onUploadSuccess, onError }) => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      setUploading(true);
      await api.post('/chat/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setFile(null);
      onUploadSuccess();
    } catch (error) {
      onError('Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <label className="block text-sm font-medium text-slate-200">Upload PDF or TXT</label>
      <input
        type="file"
        accept=".pdf,.txt"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        className="w-full text-sm text-slate-200"
      />
      <button
        type="submit"
        disabled={!file || uploading}
        className="w-full rounded bg-indigo-500 py-2 text-white hover:bg-indigo-400 disabled:opacity-50"
      >
        {uploading ? 'Uploading...' : 'Upload'}
      </button>
    </form>
  );
};

export default UploadForm;
