// @ts-check
import { defineConfig } from 'astro/config';

import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  site: 'https://ithildin.app',
  integrations: [react()],

  vite: {
    plugins: [tailwindcss()],
    optimizeDeps: {
      include: ['d3', 'd3-sankey', 'd3-dag'],
    },
    // Allow importing from content directory
    server: {
      fs: {
        allow: ['..'],
      },
    },
  },
});
