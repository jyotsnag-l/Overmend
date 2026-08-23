import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from '../src/App';

describe('App Dashboard', () => {
  it('renders the header title', () => {
    render(<App />);
    expect(screen.getByText(/Antigravity Recovery Control Plane/i)).toBeInTheDocument();
  });
});
