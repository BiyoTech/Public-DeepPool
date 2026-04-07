/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        'dp-bg-1': '#0F1729',
        'dp-bg-2': '#151D2C',
        'dp-bg-3': '#1A2332',
        'dp-bg-4': '#1E293B',
        'dp-blue': '#3B82F6',
        'dp-blue-hover': '#2563EB',
        'dp-blue-active': '#1D4ED8',
        'dp-text-1': '#F1F5F9',
        'dp-text-2': '#94A3B8',
        'dp-text-3': '#64748B',
        'dp-green': '#22C55E',
        'dp-red': '#EF4444',
        'dp-yellow': '#F59E0B',
      },
    },
  },
  plugins: [
    require('tailwindcss-animate'),
  ],
}
