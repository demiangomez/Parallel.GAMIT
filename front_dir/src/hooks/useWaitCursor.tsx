import { useEffect } from "react";

const useWaitCursor = (boolean: boolean) => {
    useEffect(() => {
        if (boolean) {
            document.body.style.cursor = "wait";
        } else {
            document.body.style.cursor = "default";
        }
    }, [boolean]);
};

export default useWaitCursor;
