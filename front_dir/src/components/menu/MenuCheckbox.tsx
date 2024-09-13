import { ReactNode } from "react";

interface MenuCheckboxProps {
    isSubmenu?: boolean;
    subMenuText?: string;
    liKey?: string;
    children?: ReactNode;
    isCheckbox: boolean;
    inputTitle: string;
    inputChecked: boolean;
    inputDisabled: boolean;
    inputText: string;
    handleChange: () => void;
}

const MenuCheckbox = ({
    subMenuText,
    liKey,
    children,
    isSubmenu,
    isCheckbox,
    inputChecked,
    inputText,
    inputTitle,
    inputDisabled,
    handleChange,
}: MenuCheckboxProps) => {
    return (
        <li
            key={liKey}
            className={`font-semibold text-lg ${isCheckbox ? "w-[150px]" : "w-fit"}`}
        >
            <a className="w-full text-center hover:cursor-default">
                {isSubmenu && isCheckbox ? (
                    <>
                        <label className="cursor-pointer label">
                            <input
                                type="checkbox"
                                className="checkbox mr-2"
                                title={inputTitle}
                                checked={inputChecked}
                                disabled={inputDisabled}
                                onChange={() => handleChange()}
                            />
                            <span className="label-text ml-2">
                                {subMenuText}
                            </span>
                        </label>
                        {children} {/* ACA VA EL UL, LI, A y INPUT */}
                    </>
                ) : isCheckbox ? (
                    <input
                        type="checkbox"
                        className="checkbox mr-2"
                        title={inputTitle}
                        checked={inputChecked}
                        disabled={inputDisabled}
                        onChange={() => handleChange()}
                    />
                ) : null}

                {inputText}
            </a>
        </li>
    );
};

export default MenuCheckbox;
