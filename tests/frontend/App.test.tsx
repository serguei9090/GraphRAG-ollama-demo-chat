import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import App from '../../frontend/src/App';

const apiMock = vi.hoisted(() => ({
  get: vi.fn(() => Promise.resolve({ data: { documents: [] } })),
  post: vi.fn(() => Promise.resolve({ data: {} }))
}));

vi.mock('../../frontend/src/lib/api', () => ({
  default: apiMock
}));

const fetchMock = vi.hoisted(() =>
  vi.fn(() => {
    const encoder = new TextEncoder();
    return Promise.resolve({
      ok: true,
      body: {
        getReader: () => {
          const read = vi
            .fn()
            .mockResolvedValueOnce({ done: false, value: encoder.encode('chunk ') })
            .mockResolvedValueOnce({ done: true, value: undefined });
          return { read };
        }
      }
    });
  })
);

beforeEach(() => {
  apiMock.get.mockClear();
  apiMock.post.mockClear();
  fetchMock.mockClear();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('App', () => {
  it('renders call to action', async () => {
    render(<App />);
    expect(await screen.findByText(/Ingest Documents/i)).toBeInTheDocument();
    expect(apiMock.get).toHaveBeenCalledWith('/chat/documents');
  });
});
