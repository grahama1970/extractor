/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: 'oklch(18% 0.02 250)',
        foreground: 'oklch(98% 0.01 250)',
        primary: 'oklch(60% 0.13 270)',
        accent: 'oklch(70% 0.17 150)'
      }
    },
  },
  plugins: [require('tailwindcss-animate')],
}
