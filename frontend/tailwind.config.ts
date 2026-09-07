import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: '#0d1117',
          panel: '#131a23',
          raised: '#1a1a2e',
          border: '#2a3441',
          muted: '#8b98a8',
          text: '#d7e0ea',
        },
        accent: {
          yellow: '#ecad0a',
          blue: '#209dd7',
          purple: '#753991',
        },
        tick: {
          up: '#2ecc71',
          down: '#ff5c5c',
        },
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', '0.9rem'],
      },
    },
  },
  plugins: [],
};

export default config;
