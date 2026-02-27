import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: "#0d1117",
          secondary: "#131722",
          card: "#1c2333",
          hover: "#252d3d",
        },
        accent: {
          green: "#26a69a",
          red: "#ef5350",
          blue: "#2196f3",
          yellow: "#ffb74d",
          orange: "#ff9800",
        },
        text: {
          primary: "#d1d4dc",
          secondary: "#787b86",
          muted: "#4a4e59",
        },
        border: {
          primary: "#2a2e39",
          secondary: "#363a45",
        },
      },
    },
  },
  plugins: [],
};

export default config;
