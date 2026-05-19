/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        hud: {
          bg: "#050a0f",
          panel: "#0a1520",
          border: "#0e3a5c",
          accent: "#00b4d8",
          accent2: "#0077b6",
          glow: "#00e5ff",
          text: "#caf0f8",
          muted: "#5a8fa3",
          danger: "#ef233c",
          success: "#06d6a0",
        },
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "'Fira Code'", "monospace"],
      },
      boxShadow: {
        glow: "0 0 12px rgba(0, 229, 255, 0.4)",
        "glow-lg": "0 0 24px rgba(0, 229, 255, 0.3)",
      },
    },
  },
  plugins: [
    function ({ addUtilities }) {
      addUtilities({ ".scrollbar-hide": { "-ms-overflow-style": "none", "scrollbar-width": "none", "&::-webkit-scrollbar": { display: "none" } } });
    },
  ],
};
