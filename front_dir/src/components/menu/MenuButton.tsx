interface MenuButtonProps {
    setShowMenu: React.Dispatch<
        React.SetStateAction<
            | {
                  type: string;
                  show: boolean;
              }
            | undefined
        >
    >;
    showMenu: { type: string; show: boolean } | undefined;
    typeKey: string;
}

const MenuButton = ({ setShowMenu, showMenu, typeKey }: MenuButtonProps) => {
    return (
        <div className="menu">
            <li
                onClick={() =>
                    setShowMenu({
                        type: typeKey,
                        show:
                            showMenu?.show !== undefined
                                ? !showMenu?.show
                                : true,
                    })
                }
            >
                <details open>
                    <summary></summary>
                </details>
            </li>
        </div>
    );
};

export default MenuButton;
