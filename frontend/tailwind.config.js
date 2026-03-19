/** @type {import('tailwindcss').Config} */
module.exports = {
    content: ['./src/**/*.{js,jsx,ts,tsx}'],
    theme: {
        extend: {
            colors: {
                dashboard: {
                    blue: {
                        DEFAULT: '#0ea5e9',
                        dark: '#0284c7',
                        soft: '#e0f2fe',
                    },
                    green: {
                        DEFAULT: '#10b981',
                        dark: '#047857',
                        soft: '#dcfce7',
                    },
                    red: {
                        DEFAULT: '#ef4444',
                        dark: '#b91c1c',
                        soft: '#fee2e2',
                    },
                    light: {
                        DEFAULT: '#f7fafc',
                        muted: '#eef5ff',
                        elevated: '#ffffff',
                    },
                },
                // Backward-compatible aliases used across current components/pages.
                primary: {
                    DEFAULT: '#0ea5e9',
                    dark: '#0284c7',
                    soft: '#e0f2fe',
                },
                secondary: {
                    DEFAULT: '#14b8a6',
                    dark: '#0f766e',
                    soft: '#ccfbf1',
                },
                success: {
                    DEFAULT: '#10b981',
                    soft: '#dcfce7',
                    text: '#047857',
                },
                error: {
                    DEFAULT: '#ef4444',
                    soft: '#fee2e2',
                    text: '#b91c1c',
                },
                warning: {
                    DEFAULT: '#f59e0b',
                    soft: '#fef3c7',
                    text: '#b45309',
                },
                background: {
                    DEFAULT: '#f7fafc',
                    muted: '#eef5ff',
                    elevated: '#ffffff',
                },
                ink: {
                    DEFAULT: '#0f172a',
                    muted: '#475569',
                    subtle: '#94a3b8',
                },
            },
            fontFamily: {
                sans: ['IBM Plex Sans', 'Segoe UI', 'ui-sans-serif', 'system-ui', 'sans-serif'],
                display: ['Manrope', 'IBM Plex Sans', 'ui-sans-serif', 'system-ui', 'sans-serif'],
            },
            boxShadow: {
                card: '0 10px 30px rgba(15, 23, 42, 0.08)',
                soft: '0 6px 20px rgba(15, 23, 42, 0.07)',
            },
            borderRadius: {
                card: '1rem',
                panel: '1.5rem',
            },
        },
    },
    plugins: [],
};
