import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0f1117',
        panel: '#161a22',
        panel2: '#1c2130',
        border: '#262c3a',
        accent: '#7cffb7',
        warn: '#ffd06b',
        danger: '#ff6b6b',
        muted: '#8b94a8',
        text: '#e7ebf3',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
};
export default config;
