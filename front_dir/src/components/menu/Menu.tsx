import { ReactNode } from "react";

interface MenuProps {
    absolute?: boolean;
    children: ReactNode;
}

const Menu = ({ children, absolute }: MenuProps) => {
    return (
        <ul
            tabIndex={0}
            className={`menu overflow-x-hidden items-center max-h-64 mt-2 ${absolute ? "absolute w-5/12 z-[100]" : ""}
             bg-neutral-content rounded-box overflow-y-auto divide-y-2 divide-base-100`}
            style={{ flexWrap: "nowrap" }}
        >
            {children}
        </ul>
    );
};

export default Menu;
