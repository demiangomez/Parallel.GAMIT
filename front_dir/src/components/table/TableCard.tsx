import { ReactNode } from "react";

interface TableCardProps {
    title: string;
    size?: string;
    addButton?: boolean;
    addButtonTitle?: string;
    modalTitle?: string;
    setModals?: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
    children: ReactNode;
    secondAddButton?: boolean;
    secondAddButtonTitle?: string;
    secondModalTitle?: string;
}

const TableCard = ({
    title,
    size,
    addButton,
    modalTitle,
    addButtonTitle,
    setModals,
    children,
    secondAddButton,
    secondAddButtonTitle,
    secondModalTitle,
}: TableCardProps) => {
    return (
        <div
            className={`flex flex-col ${size ? "" : "w-fit"}`}
            style={
                size && title.includes("Station")
                    ? { width: "750px" }
                    : { width: size }
            }
        >
            <div className="card bg-base-200 p-4 space-y-2 h-full">
                <div className="flex w-full justify-between">
                    <h2 className="card-title">{title}</h2>
                    <div className="flex flex-row justify-end gap-3 items-center">
                        {secondAddButton ? (
                            <div className="w-6/12 flex justify-end space-x-2">
                                <button
                                    className="btn btn-neutral self-end no-animation"
                                    onClick={() =>
                                        setModals &&
                                        setModals({
                                            show: true,
                                            title: secondModalTitle ?? "",
                                            type: "add",
                                        })
                                    }
                                >
                                    {secondAddButtonTitle}
                                </button>
                            </div>
                        ) : null}
                        {addButton ? (
                            <div className="w-6/12 flex justify-end space-x-2">
                                <button
                                    className="btn btn-neutral self-end no-animation"
                                    onClick={() =>
                                        setModals &&
                                        setModals({
                                            show: true,
                                            title: modalTitle ?? "",
                                            type: "add",
                                        })
                                    }
                                >
                                    {addButtonTitle}
                                </button>
                            </div>
                        ) : null}
                    </div>
                </div>
                {children}
            </div>
        </div>
    );
};

export default TableCard;
