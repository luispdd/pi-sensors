/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{html,ts}",
  ],
  theme: {
    extend: {
      colors: {
        page: 'var(--bg-page)',
        rail: 'var(--bg-rail)',
        card: {
          DEFAULT: 'var(--bg-card)',
          hover: 'var(--bg-card-hover)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          hover: 'var(--accent-hover)',
        },
        'text-primary': 'var(--text-primary)',
        'text-muted': 'var(--text-muted)',
        'success-fg': 'var(--success-fg)',
        'success-bg': 'var(--success-bg)',
        'danger-fg': 'var(--danger-fg)',
        'danger-bg': 'var(--danger-bg)',
        'warning-fg': 'var(--warning-fg)',
        'warning-bg': 'var(--warning-bg)',
        'metric-temperature': 'var(--metric-temperature)',
        'metric-humidity': 'var(--metric-humidity)',
        'metric-light': 'var(--metric-light)',
      },
      borderColor: {
        theme: 'var(--border)',
        divider: 'var(--divider)',
        accent: 'var(--accent)',
      },
    },
  },
  plugins: [],
}
