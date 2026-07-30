/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#070604",
        surface: "#14110d",
        primary: "#c8894d",
        secondary: "#6f675b",
        accent: "#e2b06e",
        text: "#eee4d3",
        muted: "#a89e8e",
        slate: {
          50: "#f4ecdf",
          100: "#eee4d3",
          200: "#d8cdbd",
          300: "#c0b5a5",
          400: "#a89e8e",
          500: "#81786b",
          600: "#6f675b",
          700: "#3d382f",
          800: "#1a1712",
          900: "#0d0b08",
          950: "#070604",
        },
        cyan: {
          300: "#efc184",
          400: "#e2b06e",
          500: "#c8894d",
          600: "#9d6637",
        },
        emerald: {
          300: "#a7c0ab",
          400: "#83a38a",
          500: "#6e8d76",
          600: "#56705d",
        },
        amber: {
          300: "#efc184",
          400: "#e2b06e",
          500: "#c8894d",
          600: "#9d6637",
        },
        red: {
          300: "#d59486",
          400: "#c37b6d",
          500: "#b86f60",
          600: "#8e5147",
          900: "#3a1f1a",
        },
        blue: {
          400: "#d7a15e",
          500: "#c8894d",
          600: "#9d6637",
        },
        violet: {
          400: "#c8a773",
          500: "#ad854f",
          600: "#846338",
        },
      }
    },
  },
  plugins: [],
}
