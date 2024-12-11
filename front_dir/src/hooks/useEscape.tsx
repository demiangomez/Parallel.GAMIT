import { useEffect } from "react";

const useEscape = (callback: () => void) => {
    useEffect(() => {
        const handleEsc = (event: { key: string }) => {
            if (event.key === "Escape") {
                callback();
            }
        };
        window.addEventListener("keydown", handleEsc);

        return () => {
            window.removeEventListener("keydown", handleEsc);
        };
    }, [callback]);
};

export default useEscape;
