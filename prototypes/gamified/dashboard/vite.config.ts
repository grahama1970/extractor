import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Read PORT from env to align with orchestrator expectations
const port = Number(process.env.PORT || process.env.VITE_PORT || 5199)

export default defineConfig({
  plugins: [react()],
  server: {
    port,
    strictPort: true,
  },
})

