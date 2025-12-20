/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "../../templates/**/*.html",
    "../../**/templates/**/*.html",
    "./src/**/*.{html,js,jsx,ts,tsx,css}",
  ],
  plugins: [require("daisyui")],
  daisyui: {
  themes: [
    "corporate",
    "business",
    "winter",
    "luxury",
    "dim",
    "night",
    "forest",
    "dracula",
    "abyss"
    ],
  },
};
