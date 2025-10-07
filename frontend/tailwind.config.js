/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{ts,tsx,js,jsx}'
  ],
  theme: {
    extend: {
      colors: {
        background: '#FAFAFA',
        surface: '#FFFFFF',
        primary: '#3457D5',
        'primary-dark': '#2C49B8',
        'neutral-dark': '#1D1D1D',
        muted: '#6F7380',
        subtle: '#E8ECFF'
      }
    }
  },
  plugins: []
};
