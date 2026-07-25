/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['system-ui', '-apple-system', '"Segoe UI"', 'sans-serif'],
      },
      colors: {
        // Brand ramp — the sequential blue from the validated data-viz palette.
        brand: {
          50: "#f0f6fe",
          100: "#cde2fb",
          200: "#9ec5f4",
          300: "#6da7ec",
          400: "#3987e5",
          500: "#2a78d6",
          600: "#256abf",
          700: "#1c5cab",
          800: "#184f95",
          900: "#0d366b",
        },
        // Sidebar / chrome plane.
        ink: {
          700: "#1e2235",
          800: "#171a29",
          900: "#0f111c",
        },
        // Fixed status palette — never themed, never reused as a series color.
        status: {
          good: "#0ca30c",
          warning: "#fab219",
          serious: "#ec835a",
          critical: "#d03b3b",
        },
        // Categorical series slots, in validated order.
        series: {
          1: "#2a78d6",
          2: "#eb6834",
          3: "#1baf7a",
        },
        surface: "#fcfcfb",
        plane: "#f6f7fb",
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.125rem",
        "3xl": "1.5rem",
      },
      boxShadow: {
        card: "0 1px 2px rgb(16 24 40 / 0.04), 0 1px 3px rgb(16 24 40 / 0.06)",
        lift: "0 12px 24px -8px rgb(16 24 40 / 0.14), 0 4px 8px -4px rgb(16 24 40 / 0.06)",
        glow: "0 8px 20px -6px rgb(42 120 214 / 0.5)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.35s cubic-bezier(0.16, 1, 0.3, 1) both",
        shimmer: "shimmer 1.6s infinite",
      },
    },
  },
  plugins: [],
};
