/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Bricolage Grotesque", "Manrope", "ui-sans-serif", "sans-serif"],
        sans: ["Manrope", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      keyframes: {
        rise: {
          from: { opacity: "0", transform: "translateY(14px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "ember-drift": {
          "0%, 100%": { transform: "translate(0, 0) scale(1)", opacity: "0.5" },
          "50%": { transform: "translate(2%, -4%) scale(1.06)", opacity: "0.8" },
        },
        "bar-fill": {
          from: { width: "0%" },
        },
        shimmer: {
          from: { backgroundPosition: "200% 0" },
          to: { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        rise: "rise 0.7s cubic-bezier(0.22, 1, 0.36, 1) both",
        "ember-drift": "ember-drift 9s ease-in-out infinite",
        "bar-fill": "bar-fill 1.2s cubic-bezier(0.22, 1, 0.36, 1) both",
        shimmer: "shimmer 3.5s linear infinite",
      },
    },
  },
  plugins: [],
};
