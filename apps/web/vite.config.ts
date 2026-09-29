import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig({
  plugins: [svelte(), tailwindcss()],
  server: {
    proxy: {
      '/api':
        process.env.API_PROXY_TARGET || process.env.LEADFLOW_API_URL || 'http://127.0.0.1:8000',
    },
  },
});
