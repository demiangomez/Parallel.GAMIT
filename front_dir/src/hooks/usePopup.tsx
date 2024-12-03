import { useState } from "react";

export const usePopup = (timeout = 3000) => {
    const [showPopup, setShowPopup] = useState(false);

    const show = () => {
        setShowPopup(true);

        setTimeout(() => {
            setShowPopup(false);
        }, timeout);
    };

    return { showPopup, show };
};

export default usePopup;
