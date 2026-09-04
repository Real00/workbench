import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        timeout: 600_000,
        proxyTimeout: 600_000,
        configure(proxy) {
          proxy.on('proxyRes', (proxyRes, _req, res) => {
            if (!String(proxyRes.headers['content-type'] ?? '').includes('text/event-stream')) return
            proxyRes.headers['cache-control'] = 'no-cache, no-transform'
            proxyRes.headers['x-accel-buffering'] = 'no'
            const write = res.write.bind(res)
            res.write = ((chunk: unknown, encoding?: unknown, callback?: unknown) => {
              const ok = write(chunk as never, encoding as never, callback as never)
              const flushable = res as typeof res & { flush?: () => void }
              flushable.flush?.()
              return ok
            }) as typeof res.write
          })
        },
      },
    },
  },
})
