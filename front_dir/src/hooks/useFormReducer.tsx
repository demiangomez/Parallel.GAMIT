import { useCallback, useReducer } from "react";

type SetValues = {
    type: "set";
    payload: Record<string, any>;
};

type ChangeValueAction = {
    type: "change_value";
    payload: {
        inputName: string;
        inputValue: number | string | boolean | File | number[] | undefined | string[]
    };
};

type ChangeArrayValueAction = {
    type: "change_array_value";
    payload: {
        index: number;
        arrayName: string;
        fieldName: string;
        fieldValue: number | string | undefined;
    };
};

type ListToClearAction = {
    type: "list_to_clear";
    payload: string[];
};

type ClearAllAction = {
    type: "clear";
};

export type FormReducerAction =
    | ChangeValueAction
    | ChangeArrayValueAction
    | ListToClearAction
    | ClearAllAction
    | SetValues;

function UseFormReducer<T extends Record<string, any>>(INITIAL_STATE: T) {
    const formReducer = (state: T, action: FormReducerAction): T => {
        let newState: T;

        switch (action.type) {
            case "set": {
                newState = JSON.parse(JSON.stringify(action.payload)) as T;
                break;
            }
            case "change_value": {
                newState = { ...state };

                const keys = action.payload.inputName.split(".");
                const lastKey = keys.pop() as string;

                let currentObject: Record<string, any> = newState;

                for (const key of keys) {
                    if (typeof currentObject[key] !== "object") {
                        currentObject[key] = {};
                    }
                    currentObject = currentObject[key];
                }

                if (
                    typeof currentObject[lastKey] === "number" &&
                    typeof action.payload.inputValue !== "number"
                ) {
                    currentObject[lastKey] = parseInt(
                        action.payload.inputValue as string,
                        10,
                    );
                } else {
                    currentObject[lastKey] = action.payload.inputValue;
                }

                break;
            }
            case "change_array_value": {
                newState = { ...state };
                const array = [
                    ...(newState[action.payload.arrayName] as Array<any>),
                ];

                if (array && array[action.payload.index]) {
                    array[action.payload.index] = {
                        ...array[action.payload.index],
                        [action.payload.fieldName]: action.payload.fieldValue,
                    };
                }

                newState = {
                    ...newState,
                    [action.payload.arrayName]: array,
                } as T;
                break;
            }
            case "list_to_clear": {
                newState = { ...state };
                action.payload.forEach((n: keyof T) => {
                    newState[n] = Array.isArray(INITIAL_STATE[n])
                        ? ([...(INITIAL_STATE[n] as Array<any>)] as T[typeof n])
                        : typeof INITIAL_STATE[n] === "object"
                          ? ({
                                ...(INITIAL_STATE[n] as Record<string, any>),
                            } as T[typeof n])
                          : INITIAL_STATE[n];
                });
                break;
            }
            case "clear": {
                newState = JSON.parse(JSON.stringify(INITIAL_STATE));
                break;
            }
            default:
                newState = state;
                break;
        }

        return newState;
    };

    const [inputValues, dispatch] = useReducer(formReducer, INITIAL_STATE);

    const clearForm = useCallback(() => dispatch({ type: "clear" }), []);

    const changeArrayValue = useCallback(
        (
            index: number,
            arrayName: string,
            fieldName: string,
            fieldValue: number | string | any | undefined,
        ) => {
            dispatch({
                type: "change_array_value",
                payload: { index, arrayName, fieldName, fieldValue },
            });
        },
        [dispatch],
    );

    return {
        formState: inputValues,
        clearForm,
        changeArrayValue,
        dispatch,
    };
}

export default UseFormReducer;
