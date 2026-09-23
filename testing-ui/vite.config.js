import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 2134,
    strictPort: true,
    host: true,
  },
  preview: {
    port: 2134,
    strictPort: true,
    host: true,
  },
});
