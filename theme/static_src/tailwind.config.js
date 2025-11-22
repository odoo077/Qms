/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "../../templates/**/*.html",
    "../../**/templates/**/*.html",
    "./src/**/*.{html,js,jsx,ts,tsx,css}",
  ],
  plugins: [require("daisyui")],
  daisyui: {
    themes: ["light", "dark"],  // <— keep it very simple for testing
  },
};
