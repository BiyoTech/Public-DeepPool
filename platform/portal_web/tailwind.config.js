/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // 品牌蓝色渐变
        'dp-blue': '#3B82F6',
        'dp-blue-dark': '#2563EB',
        'dp-blue-deeper': '#1D4ED8',
        // 品牌紫色渐变
        'dp-purple': '#8B5CF6',
        'dp-purple-dark': '#7C3AED',
        // 文字色阶
        'dp-title': '#0F172A',
        'dp-body': '#334155',
        'dp-muted': '#64748B',
        'dp-placeholder': '#94A3B8',
        // 背景色阶
        'dp-bg-white': '#FFFFFF',
        'dp-bg-gray': '#F8FAFC',
        'dp-bg-section': '#F1F5F9',
        // 边框
        'dp-border': '#E2E8F0',
        // 页脚深色
        'dp-footer': '#0F172A',
        'dp-footer-line': '#334155',
      },
      fontFamily: {
        sans: ['"PingFang SC"', '"Helvetica Neue"', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [
    require('tailwindcss-animate'),
  ],
}
