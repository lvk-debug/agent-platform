/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#1890ff',
          hover: '#40a9ff',
          bg: '#e6f7ff',
        },
        gradient: {
          start: '#667eea',
          end: '#764ba2',
        },
        border: {
          DEFAULT: '#f0f0f0',
          light: '#f5f5f5',
        },
        page: '#f5f5f5',
        sidebar: '#ffffff',
        header: '#ffffff',
        text: {
          primary: '#333333',
          secondary: '#999999',
          muted: '#888888',
        },
      },
      borderRadius: {
        card: '12px',
        button: '8px',
        bubble: '12px',
      },
      boxShadow: {
        card: '0 8px 24px rgba(0, 0, 0, 0.15)',
        header: '0 1px 4px rgba(0, 21, 41, 0.08)',
        sider: '2px 0 8px rgba(0, 0, 0, 0.05)',
        bubble: '0 1px 2px rgba(0, 0, 0, 0.1)',
      },
      spacing: {
        header: '64px',
        sider: '200px',
        'sider-collapsed': '80px',
      },
    },
  },
  plugins: [],
}
