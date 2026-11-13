/** @type {import('tailwindcss').Config} */
const v = (name) => `hsl(var(--${name}) / <alpha-value>)`;
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: v("background"),
        foreground: v("foreground"),
        card: v("card"),
        muted: v("muted"),
        "muted-foreground": v("muted-foreground"),
        border: v("border"),
        ring: v("ring"),
        primary: v("primary"),
        "primary-foreground": v("primary-foreground"),
        accent: v("accent"),
        success: v("success"),
        warning: v("warning"),
        danger: v("danger"),
        k: {
          prompt: v("k-prompt"),
          skill: v("k-skill"),
          subagent: v("k-subagent"),
          tool: v("k-tool"),
          guard: v("k-guard"),
          edit: v("k-edit"),
          response: v("k-response"),
          compact: v("k-compact"),
          workflow: v("k-workflow"),
        },
      },
      borderRadius: { lg: "0.6rem", md: "0.45rem", sm: "0.3rem" },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      keyframes: {
        pulseRing: { "0%": { boxShadow: "0 0 0 0 hsl(var(--primary) / 0.5)" }, "100%": { boxShadow: "0 0 0 8px hsl(var(--primary) / 0)" } },
      },
      animation: { "pulse-ring": "pulseRing 1.4s ease-out infinite" },
    },
  },
  plugins: [],
};
