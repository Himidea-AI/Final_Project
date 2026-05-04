/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Pretendard', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        // System A — 배경/구조
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        card: { DEFAULT: 'var(--card)', foreground: 'var(--card-foreground)' },
        popover: { DEFAULT: 'var(--popover)', foreground: 'var(--popover-foreground)' },
        primary: { DEFAULT: 'var(--primary)', foreground: 'var(--primary-foreground)' },
        secondary: { DEFAULT: 'var(--secondary)', foreground: 'var(--secondary-foreground)' },
        muted: { DEFAULT: 'var(--muted)', foreground: 'var(--muted-foreground)' },
        accent: { DEFAULT: 'var(--accent)', foreground: 'var(--accent-foreground)' },
        destructive: { DEFAULT: 'var(--destructive)', foreground: 'var(--destructive-foreground)' },
        border: 'var(--border)',
        input: 'var(--input)',
        ring: 'var(--ring)',

        // System B — Status (12색 alias)
        success: { DEFAULT: 'var(--success)', foreground: 'var(--success-foreground)' },
        warning: { DEFAULT: 'var(--warning)', foreground: 'var(--warning-foreground)' },
        danger: { DEFAULT: 'var(--danger)', foreground: 'var(--danger-foreground)' },

        // System B — Chart 4색 (4동 categorical 비교)
        chart: {
          1: 'var(--chart-1)',
          2: 'var(--chart-2)',
          3: 'var(--chart-3)',
          4: 'var(--chart-4)',
        },

        // System B — Ranking 4-tier (Deep Blue Sequential, ordinal: winner→4위)
        rank: {
          1: 'var(--rank-1)',
          2: 'var(--rank-2)',
          3: 'var(--rank-3)',
          4: 'var(--rank-4)',
        },

        // System B — Decoration (큰 면적 장식 only)
        decor: {
          cream: 'var(--decor-cream)',
          cyan: 'var(--decor-cyan)',
          yellow: 'var(--decor-yellow)',
          'light-pink': 'var(--decor-light-pink)',
          'hot-pink': 'var(--decor-hot-pink)',
          'starburst-pink': 'var(--decor-starburst-pink)',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
    },
  },
  plugins: [],
};
