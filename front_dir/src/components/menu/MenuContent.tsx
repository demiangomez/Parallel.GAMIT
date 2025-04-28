import { CheckIcon } from "@heroicons/react/24/outline";
import { FormReducerAction } from "@hooks/useFormReducer";

interface MenuContentProps {
    value: string;
    multiple?: boolean;
    multipleSelected?: any | undefined;
    alterValue?: string;
    typeKey: string;
    disabled?: boolean;
    alterFunction?: () => void;
    setMultipleSelected?: React.Dispatch<
        React.SetStateAction<string[] | undefined>
    >;
    dispatch?: (value: FormReducerAction) => void;
    alterFunctionWithValue?: (value: string) => void;
    setShowMenu: React.Dispatch<
        React.SetStateAction<
            | {
                  type: string;
                  show: boolean;
              }
            | undefined
        >
    >;
}

const MenuContent = ({
    value,
    multiple,
    multipleSelected,
    alterValue,
    typeKey,
    disabled,
    dispatch,
    alterFunction,
    setMultipleSelected,
    setShowMenu,
    alterFunctionWithValue,
}: MenuContentProps) => {
    const handleClick = () => {
        const newValue = alterValue ? alterValue : value;
        if(alterFunctionWithValue){
            alterFunctionWithValue(newValue);
            setShowMenu(undefined)
            return;
        }
        else if (multiple) {
            setMultipleSelected &&
                setMultipleSelected((prev) => {
                    if (prev) {
                        if (prev.includes(value)) {
                            return prev.filter((v) => v !== value);
                        } else {
                            return [...prev, value];
                        }
                    } else {
                        return [value];
                    }
                });
        }
        else{
            dispatch &&
            !setMultipleSelected &&
            dispatch({
                type: "change_value",
                payload: {
                    inputName: typeKey,
                    inputValue: newValue,
                },
            });
            !multiple && setShowMenu(undefined);
        }
        
    };

    return (
        <li
            className={`py-2 font-semibold text-lg w-full ${disabled ? "disabled" : ""}`}
        >
            <button
                className={`w-full justify-center text-center ${disabled ? "btn-disabled" : ""}`}
                type="button"
                onClick={() => {
                    dispatch ? handleClick() : alterFunction && alterFunction();
                }}
            >
                {value}{" "}
                {multiple && multipleSelected.includes(value) ? (
                    <span className="absolute right-10">
                        <CheckIcon className="size-6" />
                    </span>
                ) : null}
            </button>
        </li>
    );
};

export default MenuContent;
