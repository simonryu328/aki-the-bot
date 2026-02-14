const konstaConfig = require('konsta/config');

/** @type {import('tailwindcss').Config} */
module.exports = konstaConfig({
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class', // or 'media' or 'class'
  theme: {
    extend: {
      colors: {
        'space-black': '#0b0d17',
        'space-dark': '#151922',
        'space-accent': '#d0d6f9',
        'star-white': '#ffffff',
      }
    },
  },
  plugins: [],
});
