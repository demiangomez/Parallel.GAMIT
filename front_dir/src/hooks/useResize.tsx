import { useState, useEffect } from "react";

const useResize = () => {
    const [widthResponsive, setWidthResponsive] = useState(
        window.innerWidth < 1200,
    );

    const handleResize = () => {
        setWidthResponsive(window.innerWidth < 1200);
    };

    useEffect(() => {
        window.addEventListener("resize", handleResize);

        return () => {
            window.removeEventListener("resize", handleResize);
        };
    }, []);
    return widthResponsive;
};

export default useResize;
