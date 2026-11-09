export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0B1020', bg2: '#111827', panel: '#172033',
        accent: '#38BDF8', accent2: '#34D399',
        ink: '#F8FAFC', muted: '#94A3B8', line: '#263449',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      keyframes: {
        fade: { '0%': { opacity: '0', transform: 'translateY(4px)' }, '100%': { opacity: '1', transform: 'none' } },
        pulseline: { '0%,100%': { opacity: '0.35' }, '50%': { opacity: '1' } },
      },
      animation: { fade: 'fade .25s ease-out', pulseline: 'pulseline 1.6s ease-in-out infinite' },
    },
  },
  plugins: [],
}
