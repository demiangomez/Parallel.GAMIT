import { useState } from "react";

export const useLocalStorage = (key: string, initialValue: string | null) => {
    //TRAER DEL LOCALSTORAGE LA KEY Y EL VALOR INICIAL

    const [storedValue, setStoredValue] = useState(() => {
        try {
            const item = window.localStorage.getItem(key);
            return item ? item : initialValue;
        } catch (error) {
            console.error(error);
            return initialValue;
        }
    });

    // GUARDAR EL VALOR EN EL LOCALSTORAGE

    const setValue = (value: string | null) => {
        try {
            if (value === null) {
                setStoredValue(null);
                window.localStorage.removeItem(key);
                return;
            } else {
                setStoredValue(value);
                window.localStorage.setItem(key, value);
            }
        } catch (error) {
            console.error(error);
            if (error instanceof DOMException && error.code === 22) {
                console.error("LocalStorage is full, please empty data");
            }
        }
    };

    return [storedValue, setValue] as const;
};

export default useLocalStorage;
