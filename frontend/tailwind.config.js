/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: "#0F172A",
          primary: "#6366F1",
          secondary: "#10B981",
        }
      }
    },
  },
  plugins: [],
}
