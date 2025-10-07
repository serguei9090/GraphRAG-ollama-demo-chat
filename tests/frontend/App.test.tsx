import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import App from '../../frontend/src/App';

vi.mock('axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { documents: [] } })),
    post: vi.fn(() => Promise.resolve({ data: {} }))
  }
}));

vi.stubGlobal('fetch', () =>
  Promise.resolve({
    body: {
      getReader: () => ({
        read: async () => ({ done: true })
      })
    }
  })
);

describe('App', () => {
  it('renders call to action', () => {
    render(<App />);
    expect(screen.getByText(/Ingest Documents/i)).toBeInTheDocument();
  });
});
