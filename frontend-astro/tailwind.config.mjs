function withOpacity(variableName) {
  return ({ opacityValue }) => {
    if (opacityValue !== undefined) {
      return `rgba(var(${variableName}), ${opacityValue})`
    }
    return `rgb(var(${variableName}))`
  }
}

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: withOpacity('--color-bg-primary'),
          secondary: withOpacity('--color-bg-secondary'),
          card: withOpacity('--color-bg-card'),
          'card-hover': withOpacity('--color-bg-card-hover'),
          input: withOpacity('--color-bg-input'),
        },
        accent: {
          primary: withOpacity('--color-accent-primary'),
          'primary-light': withOpacity('--color-accent-primary-light'),
          secondary: withOpacity('--color-accent-secondary'),
          success: withOpacity('--color-accent-success'),
          warning: withOpacity('--color-accent-warning'),
          danger: withOpacity('--color-accent-danger'),
        },
        text: {
          primary: withOpacity('--color-text-primary'),
          secondary: withOpacity('--color-text-secondary'),
          muted: withOpacity('--color-text-muted'),
          accent: withOpacity('--color-text-accent'),
        },
        border: {
          subtle: 'rgba(var(--color-accent-primary), 0.12)',
          default: 'rgba(var(--color-accent-primary), 0.2)',
          active: 'rgba(var(--color-accent-primary), 0.5)',
        }
      },
      backgroundImage: {
        'gradient-primary': 'linear-gradient(135deg, rgb(var(--color-accent-primary)) 0%, rgb(var(--color-accent-primary-light)) 50%, rgb(var(--color-accent-secondary)) 100%)',
        'gradient-card': 'linear-gradient(145deg, rgba(var(--color-accent-primary),0.08) 0%, rgba(var(--color-accent-secondary),0.04) 100%)',
        'gradient-glow': 'radial-gradient(ellipse at 50% 0%, rgba(var(--color-accent-primary),0.15) 0%, transparent 60%)',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', 'monospace'],
      },
      animation: {
        'pulse-glow': 'pulse-glow 3s ease-in-out infinite',
        'spin-slow': 'spin 1.5s linear infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 30px rgba(99, 102, 241, 0.15)' },
          '50%': { boxShadow: '0 0 50px rgba(99, 102, 241, 0.25)' },
        }
      }
    },
  },
  plugins: [],
}
