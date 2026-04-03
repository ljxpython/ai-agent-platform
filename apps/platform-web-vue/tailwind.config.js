/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
          950: '#172554'
        },
        dark: {
          300: '#94a3b8',
          400: '#64748b',
          500: '#475569',
          600: '#334155',
          700: '#1e293b',
          800: '#172033',
          900: '#101826',
          950: '#0b1220'
        },
        workspace: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
          950: '#172554'
        },
        surface: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617'
        }
      },
      boxShadow: {
        shell: '0 18px 48px rgba(15, 23, 42, 0.08)',
        panel: '0 12px 28px rgba(15, 23, 42, 0.08)',
        soft: '0 1px 2px rgba(15, 23, 42, 0.06)',
        card: '0 8px 30px rgba(15, 23, 42, 0.06)',
        'card-hover': '0 18px 40px rgba(15, 23, 42, 0.1)',
        glass: '0 12px 32px rgba(15, 23, 42, 0.12)',
        glow: '0 10px 30px rgba(37, 99, 235, 0.22)'
      },
      backgroundImage: {
        'workspace-glow':
          'radial-gradient(circle at top left, rgba(37, 99, 235, 0.12), transparent 28%), radial-gradient(circle at top right, rgba(59, 130, 246, 0.08), transparent 24%)',
        'mesh-gradient':
          'radial-gradient(circle at 0% 0%, rgba(59, 130, 246, 0.12), transparent 30%), radial-gradient(circle at 100% 0%, rgba(14, 165, 233, 0.08), transparent 24%), linear-gradient(180deg, rgba(248, 250, 252, 0.96), rgba(241, 245, 249, 0.98))'
      },
      borderRadius: {
        '4xl': '2rem'
      }
    }
  },
  plugins: []
}
