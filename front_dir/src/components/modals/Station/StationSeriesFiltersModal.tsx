import { Modal } from "@componentsReact";
import { useFormReducer } from "@hooks";
import { SERIES_FILTERS_STATE } from "@utils/reducerFormStates";
import { useEffect } from "react";

interface Props {
    filters: Record<keyof typeof SERIES_FILTERS_STATE, any>;
    setFilters: React.Dispatch<
        React.SetStateAction<Record<keyof typeof SERIES_FILTERS_STATE, any>>
    >;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
    handleSubmit: () => void;
    handleCleanFilters: () => void;
}

const StationSeriesFiltersModal = ({
    filters,
    setFilters,
    setStateModal,
    handleSubmit,
    handleCleanFilters,
}: Props) => {
    const { formState, dispatch } = useFormReducer(SERIES_FILTERS_STATE);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { value, name, type, checked } = e.target;

        if (name.includes("date") || name === "solution") {
            dispatch({
                type: "change_value",
                payload: {
                    inputName: name,
                    inputValue: value,
                },
            });

            setFilters((prev) => ({
                ...prev,
                [name]: value,
            }));
            return;
        }

        const inputValue = type === "checkbox" ? checked : value;

        dispatch({
            type: "change_value",
            payload: {
                inputName: name,
                inputValue,
            },
        });

        setFilters((prev) => ({
            ...prev,
            [name]: inputValue,
        }));
    };

    const handleSubmitForm = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        handleSubmit();
    };

    useEffect(() => {
        if (Object.values(filters).some((r) => r.length > 0)) {
            dispatch({
                type: "set",
                payload: filters,
            });
        }
    }, [filters]);

    return (
        <Modal
            close={false}
            modalId={"SeriesFilters"}
            size={"xl"}
            setModalState={setStateModal}
        >
            <form
                className="flex flex-col w-full space-y-4"
                onSubmit={handleSubmitForm}
            >
                <div className="grid grid-cols-1 grid-flow-dense gap-2">
                    <div className="card bg-base-200 grow shadow-xl">
                        <h2 className="card-title border-b-2 border-base-300 p-2">
                            Parameters
                        </h2>

                        <div className="card-body">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="flex flex-col text-sm space-y-2 my-2 overflow-x-auto">
                                    <div className="join">
                                        <label
                                            htmlFor="date_start"
                                            className="input join-item input-bordered flex items-center w-full"
                                        >
                                            <input
                                                type="date"
                                                value={formState["date_start"]}
                                                name="date_start"
                                                id="date_start"
                                                className="w-full"
                                                onChange={(e) => {
                                                    handleChange(e);
                                                }}
                                            />
                                        </label>
                                        <span
                                            className="join-item px-6 text-lg place-content-center bg-neutral-content border border-neutral-300 
                                "
                                        >
                                            to
                                        </span>
                                        <label
                                            htmlFor="date_end"
                                            className="input join-item input-bordered flex items-center w-full"
                                        >
                                            <input
                                                type="date"
                                                value={formState["date_end"]}
                                                name="date_end"
                                                id="date_end"
                                                className="w-full"
                                                onChange={(e) => {
                                                    handleChange(e);
                                                }}
                                            />
                                        </label>
                                    </div>
                                </div>
                                {Object.entries(formState).map(
                                    ([key, value]) => {
                                        if (
                                            key === "date_start" ||
                                            key === "date_end" ||
                                            key === "solution" ||
                                            key === "stack"
                                        )
                                            return null;

                                        return (
                                            <div
                                                key={key}
                                                className="flex flex-col text-sm space-y-2 my-2 overflow-x-auto justify-center
                                    "
                                            >
                                                <label
                                                    htmlFor={key}
                                                    className="input input-bordered flex items-center w-full space-x-4"
                                                >
                                                    <span className="font-bold">
                                                        {key
                                                            .replace(/_/g, " ")
                                                            .toUpperCase()}
                                                    </span>
                                                    <input
                                                        type="checkbox"
                                                        className="checkbox"
                                                        checked={
                                                            value as boolean
                                                        }
                                                        name={key}
                                                        id={key}
                                                        onChange={(e) => {
                                                            handleChange(e);
                                                        }}
                                                    />
                                                </label>
                                            </div>
                                        );
                                    },
                                )}
                            </div>
                        </div>
                    </div>
                </div>
                <div className="flex w-full justify-center space-x-4 items-end">
                    <button
                        className="btn btn-success w-[200px] self-center"
                        type="submit"
                    >
                        Apply parameters
                    </button>
                    <a
                        className="link link-hover"
                        onClick={() => handleCleanFilters()}
                    >
                        Clean parameters
                    </a>
                </div>
            </form>
        </Modal>
    );
};

export default StationSeriesFiltersModal;
