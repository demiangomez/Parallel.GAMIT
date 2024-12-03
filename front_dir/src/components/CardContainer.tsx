import { PlusCircleIcon } from "@heroicons/react/24/outline";
import { ReactNode } from "react";

interface Props {
    title: string;
    titlePosition?: "center" | "start" | "end";
    height?: boolean;
    addButton?: boolean;
    addFunction?: () => void;
    children: ReactNode;
}

const CardContainer = ({
    title,
    height,
    titlePosition,
    addButton,
    addFunction,
    children,
}: Props) => {
    return (
        <div className="flex flex-col pt-6 w-full h-full">
            <div
                className={`card bg-base-200 p-4 space-y-2 ${height ? "h-[55vh]" : "h-full"} overflow-hidden`}
            >
                {title.length > 0 && (
                    <div className="w-full inline-flex">
                        <h3
                            className={`font-bold ${titlePosition ? "text-" + titlePosition : "text-center"} text-3xl my-2 grow`}
                        >
                            {title}
                        </h3>
                        {addButton && addFunction && (
                            <>
                                <label className="self-center">Add</label>
                                <button
                                    className="btn btn-ghost btn-circle ml-2"
                                    onClick={() => {
                                        addFunction();
                                    }}
                                >
                                    <PlusCircleIcon
                                        strokeWidth={1.5}
                                        stroke="currentColor"
                                        className="w-8 h-10"
                                    />
                                </button>
                            </>
                        )}
                    </div>
                )}
                <div
                    className={`w-full h-full inline-flex space-x-4 justify-center overflow-auto`}
                >
                    {children}
                </div>
            </div>
        </div>
    );
};

export default CardContainer;
