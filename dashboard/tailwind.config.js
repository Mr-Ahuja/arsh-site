/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        kite: {
          blue: "#387ED1",
          green: "#4CAF50",
          red: "#FF5722",
        },
        bg: {
          DEFAULT: "#FFFFFF",
          alt: "#F9F9F9",
        },
        ink: {
          DEFAULT: "#3C3C3C",
          muted: "#9B9B9B",
        },
        line: "#E0E0E0",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
