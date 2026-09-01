/** @type {import('tailwindcss').Config} */
const token = (name) => `rgb(var(--color-${name}) / <alpha-value>)`;

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: token('background'),
        surface: token('surface'),
        primary: token('primary'),
        secondary: token('secondary'),
        accent: token('accent'),
        text: token('text'),
        muted: token('muted'),
        slate: {
          50: token('slate-50'),
          100: token('slate-100'),
          200: token('slate-200'),
          300: token('slate-300'),
          400: token('slate-400'),
          500: token('slate-500'),
          600: token('slate-600'),
          700: token('slate-700'),
          800: token('slate-800'),
          900: token('slate-900'),
          950: token('slate-950'),
        },
        cyan: {
          100: token('cyan-100'),
          200: token('cyan-200'),
          300: token('cyan-300'),
          400: token('cyan-400'),
          500: token('cyan-500'),
          600: token('cyan-600'),
          950: token('cyan-950'),
        },
        emerald: {
          100: token('emerald-100'),
          200: token('emerald-200'),
          300: token('emerald-300'),
          400: token('emerald-400'),
          500: token('emerald-500'),
          600: token('emerald-600'),
          900: token('emerald-900'),
          950: token('emerald-950'),
        },
        amber: {
          100: token('amber-100'),
          200: token('amber-200'),
          300: token('amber-300'),
          400: token('amber-400'),
          500: token('amber-500'),
          600: token('amber-600'),
          950: token('amber-950'),
        },
        red: {
          100: token('red-100'),
          200: token('red-200'),
          300: token('red-300'),
          400: token('red-400'),
          500: token('red-500'),
          600: token('red-600'),
          900: token('red-900'),
          950: token('red-950'),
        },
        blue: {
          400: token('blue-400'),
          500: token('blue-500'),
          600: token('blue-600'),
        },
        violet: {
          200: token('violet-200'),
          300: token('violet-300'),
          400: token('violet-400'),
          500: token('violet-500'),
          600: token('violet-600'),
        },
      }
    },
  },
  plugins: [],
}
