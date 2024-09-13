import daisyui from "daisyui";

/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
        "./node_modules/react-tailwindcss-datetimepicker/dist/react-tailwindcss-datetimepicker.js",
    ],
    theme: {
        extend: {
            margin: {
                sidebar: "18rem",
                nosidebar: "8rem",
            },
            screens: {
                xs: { min: "375px", max: "639px" },
                sm: { min: "640px", max: "767px" },

                md: { min: "768px", max: "1023px" },

                lg: { min: "375px", max: "1279px" },

                xl: { min: "375px", max: "1535px" },

                "2xl": { min: "1536px" },
                "3xl": "1920px",
            },
        },
    },
    variants: {},
    plugins: [
        daisyui,
        function ({ addUtilities }) {
            const newUtilities = {
                ".scrollbar-thin": {
                    scrollbarWidth: "15px",
                    scrollbarColor:
                        "white oklch(25.3267% 0.015896 252.417568 / 1)",
                },
                ".scrollbar-webkit": {
                    "&::-webkit-scrollbar": {
                        width: "10px",
                    },
                    "&::-webkit-scrollbar-track": {
                        backgroundColor: "white",
                    },
                    "&::-webkit-scrollbar-thumb": {
                        backgroundColor:
                            "oklch(25.3267% 0.015896 252.417568 / 1)",
                        borderRadius: "20px",
                        border: "1px solid white",
                    },
                },
            };
            addUtilities(newUtilities, ["responsive", "hover"]);
        },
    ],
    daisyui: {
        themes: ["nord"],
    },
};
