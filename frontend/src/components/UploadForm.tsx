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
    <form onSubmit={handleSubmit} className="space-y-3">
      <label className="block text-sm font-medium text-surface">Upload PDF or TXT</label>
      <input
        type="file"
        accept=".pdf,.txt"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        className="w-full text-sm text-surface/80 file:mr-4 file:rounded-md file:border-0 file:bg-surface file:px-4 file:py-2 file:text-neutral-dark"
      />
      <button
        type="submit"
        disabled={!file || uploading}
        className="w-full rounded-lg bg-primary py-2 text-surface font-medium shadow hover:bg-primary-dark transition disabled:opacity-60"
      >
        {uploading ? 'Uploading...' : 'Upload'}
      </button>
    </form>
  );
};

export default UploadForm;
