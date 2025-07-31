/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['class'],
  content: [
    './pages/**/*.{ts,tsx}',
    './@/components/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  prefix: '',
  theme: {
    container: {
      center: 'true',
      padding: '2rem',
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      colors: {
        accent: {
          base: 'var(--accent-base)',
          light: 'var(--accent-light)',
          lighter: 'var(--accent-lighter)',
          dark: 'var(--accent-dark)',
          darker: 'var(--accent-darker)',
          contrast: 'var(--accent-contrast)',
        },
        color1: 'var(--color-1)',
        color2: 'var(--color-2)',
        color3: 'var(--color-3)',
        color4: 'var(--color-4)',
        color5: 'var(--color-5)',
        color6: 'var(--color-6)',
        color7: 'var(--color-7)',
        color8: 'var(--color-8)',
        color9: 'var(--color-9)',
        border: 'var(--border)',
        input: 'var(--input)',
        ring: 'var(--ring)',
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        primary: {
          DEFAULT: 'var(--primary)',
          foreground: 'var(--primary-foreground)',
        },
        secondary: {
          DEFAULT: 'var(--secondary)',
          foreground: 'var(--secondary-foreground)',
        },
        destructive: {
          DEFAULT: 'var(--destructive)',
          foreground: 'var(--destructive-foreground)',
        },
        muted: {
          DEFAULT: 'var(--muted)',
          foreground: 'var(--muted-foreground)',
        },
        popover: {
          DEFAULT: 'var(--popover)',
          foreground: 'var(--popover-foreground)',
        },
        card: {
          DEFAULT: 'var(--card)',
          foreground: 'var(--card-foreground)',
        },
        link: 'var(--link)',
        'link-hover': 'var(--link-hover)',
        // 现代化渐变色彩
        gradient: {
          from: '#667eea',
          via: '#764ba2',
          to: '#f093fb',
        },
        neon: {
          blue: '#00d4ff',
          purple: '#a855f7',
          pink: '#ec4899',
          green: '#10b981',
          orange: '#f97316',
        },
        glass: {
          light: 'rgba(255, 255, 255, 0.1)',
          dark: 'rgba(0, 0, 0, 0.1)',
        },
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar-background))',
          foreground: 'hsl(var(--sidebar-foreground))',
          primary: 'hsl(var(--sidebar-primary))',
          'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
          'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
          border: 'hsl(var(--sidebar-border))',
          ring: 'hsl(var(--sidebar-ring))',
        },
      },
      backgroundColor: {
        'primary-custom': 'var(--sciphi-primary)',
        'secondary-custom': 'var(--sciphi-secondary)',
        'accent-custom': 'var(--sciphi-accent)',
      },
      textColor: {
        link: 'var(--link)',
        'link-hover': 'var(--link-hover)',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      keyframes: {
        'accordion-down': {
          from: {
            height: '0',
          },
          to: {
            height: 'var(--radix-accordion-content-height)',
          },
        },
        'accordion-up': {
          from: {
            height: 'var(--radix-accordion-content-height)',
          },
          to: {
            height: '0',
          },
        },
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        glow: {
          '0%, 100%': { boxShadow: '0 0 5px rgba(168, 85, 247, 0.5)' },
          '50%': { boxShadow: '0 0 20px rgba(168, 85, 247, 0.8)' },
        },
        'gradient-x': {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'fade-in': 'fade-in 0.5s ease-out',
        'slide-in': 'slide-in 0.3s ease-out',
        glow: 'glow 2s ease-in-out infinite',
        'gradient-x': 'gradient-x 3s ease infinite',
      },
      boxShadow: {
        header: 'var(--header-box-shadow)',
        shadow: 'var(--shadow)',
        'shadow-hover': 'var(--shadow-hover)',
      },
    },
  },
  plugins: [require('tailwindcss-animate'), require('@tailwindcss/forms')],
};
