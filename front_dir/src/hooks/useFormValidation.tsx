import { useCallback, useState } from "react";

type FieldValidity = { [key: string]: boolean };

const useFormValidation = (fields: string[]) => {
    const [fieldValidity, setFieldValidity] = useState<FieldValidity>(
        fields.reduce((acc, field) => ({ ...acc, [field]: true }), {}),
    );

    const resetValidation = useCallback(() => {
        setFieldValidity(
            fields.reduce((acc, field) => ({ ...acc, [field]: true }), {}),
        );
    }, [fields]);

    const validateField = (
        name: string,
        value: string,
        test: (value: string) => boolean,
    ) => {
        setFieldValidity((prev) => ({ ...prev, [name]: test(value) }));
    };

    const allFieldsValid = Object.values(fieldValidity).every(Boolean);

    return { fieldValidity, allFieldsValid, validateField, resetValidation };
};

export default useFormValidation;
