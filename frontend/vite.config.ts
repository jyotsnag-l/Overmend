import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/', // Serve assets from root when deployed via FastAPI
  server: {
    port: 3000,
    host: true,
  },
  // @ts-ignore
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
    exclude: ['**/node_modules/**', '**/dist/**', '**/tests/e2e/**'],
  },
});
