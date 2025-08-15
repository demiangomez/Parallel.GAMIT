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
    filters?: Record<string, string>;
    setFilters?: (filters: Record<string, string>) => void;
    showSearch?: boolean;
    searchPlaceholder?: string;
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
    filters,
    setFilters,
    showSearch = false,
    searchPlaceholder = "Search...",
}: TableCardProps) => {
    const widthStyle = size
        ? {
              width: title.includes("Station")
                  ? Math.max(750, parseInt(size)) + "px"
                  : size,
          }
        : {};

    const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (setFilters && filters) {
            setFilters({ ...filters, search: e.target.value });
        }
    };

    return (
        <div
            className={`flex flex-col ${size ? "" : "w-fit"}`}
            style={widthStyle}
        >
            <div className="card bg-base-200 p-4 space-y-2 h-full">
                <div className="flex w-full justify-between flex-wrap gap-2">
                    <h2 className="card-title">{title}</h2>
                    <div className="flex flex-row justify-end gap-3 items-center flex-wrap">
                        {showSearch && (
                            <div className="w-64">
                                <input
                                    type="text"
                                    placeholder={searchPlaceholder}
                                    className="input input-bordered w-full"
                                    value={filters?.search || ""}
                                    onChange={handleSearchChange}
                                />
                            </div>
                        )}
                        {secondAddButton ? (
                            <div className="flex justify-end">
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
                            <div className="flex justify-end">
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
