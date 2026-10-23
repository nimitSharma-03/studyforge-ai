/** @type {import('tailwindcss').Config} */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Variable"', 'Inter', 'ui-sans-serif', 'system-ui', '-apple-system', '"Segoe UI"', 'Roboto', 'sans-serif'],
      },
      colors: {
        canvas: token('canvas'),
        surface: token('surface'),
        subtle: token('subtle'),
        line: token('line'),
        'line-strong': token('line-strong'),
        ink: token('ink'),
        body: token('body'),
        muted: token('muted'),
        navy: {
          DEFAULT: token('navy'),
          soft: token('navy-soft'),
        },
        brand: {
          50: token('brand-50'),
          100: token('brand-100'),
          200: token('brand-200'),
          300: token('brand-300'),
          500: token('brand-500'),
          600: token('brand-600'),
          700: token('brand-700'),
          800: token('brand-800'),
        },
        success: { DEFAULT: token('success'), soft: token('success-soft'), ink: token('success-ink') },
        danger: { DEFAULT: token('danger'), soft: token('danger-soft'), ink: token('danger-ink') },
        warning: { DEFAULT: token('warning'), soft: token('warning-soft'), ink: token('warning-ink') },
        info: { DEFAULT: token('info'), soft: token('info-soft'), ink: token('info-ink') },
      },
      borderRadius: {
        sm: '6px',
        DEFAULT: '8px',
        md: '8px',
        lg: '12px',
        xl: '16px',
      },
      boxShadow: {
        xs: '0 1px 2px 0 rgb(15 23 42 / 0.05)',
        card: '0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)',
        raised: '0 4px 12px -2px rgb(15 23 42 / 0.08), 0 2px 4px -2px rgb(15 23 42 / 0.05)',
        overlay: '0 24px 48px -12px rgb(15 23 42 / 0.25)',
        focus: '0 0 0 3px rgb(var(--brand-200))',
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      keyframes: {
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'slide-up': { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'none' } },
        indeterminate: { '0%': { transform: 'translateX(-100%)' }, '100%': { transform: 'translateX(250%)' } },
      },
      animation: {
        'fade-in': 'fade-in 150ms ease-out',
        'slide-up': 'slide-up 180ms ease-out',
        indeterminate: 'indeterminate 1.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
