/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        chart: {
          bg: "#0A1628",
          surface: "#12233B",
          raised: "#1A2E4A",
          line: "#24405F",
        },
        ink: {
          DEFAULT: "#E8EEF5",
          muted: "#7C93AD",
        },
        route: "#4FD1C5",
        alert: "#F0A857",
        danger: "#E8646F",
        success: "#6FCF97",
      },
      fontFamily: {
        sans: ["'IBM Plex Sans'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
    },
  },
  plugins: [],
};
