import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'
import { offline } from './offline.plugin'
import { BRAND } from './src/branding'

// The web app manifest (what makes the game installable) is written from the
// same place the game's name lives, so there is only one name to change.
function manifest(): Plugin {
  const body = () =>
    JSON.stringify(
      {
        name: BRAND.title,
        short_name: BRAND.title,
        description: BRAND.tagline,
        id: './',
        start_url: './',
        scope: './',
        display: 'standalone',
        display_override: ['fullscreen', 'standalone'],
        // The match is played on the long side; installed, the whole app stays that way.
        orientation: 'landscape',
        background_color: '#090b10',
        theme_color: '#090b10',
        categories: ['games'],
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: 'icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      null,
      2,
    )
  return {
    name: 'app-manifest',
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'manifest.json', source: body() })
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url?.split('?')[0] !== '/manifest.json') return next()
        res.setHeader('Content-Type', 'application/json')
        res.end(body())
      })
    },
  }
}

export default defineConfig({
  // Relative asset paths: the build works at "/" and under any sub-path.
  base: './',
  // `offline` goes last: it lists everything the build produced.
  plugins: [react(), manifest(), offline()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/art': 'http://127.0.0.1:8000',
      '/audio': 'http://127.0.0.1:8000',
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
})
