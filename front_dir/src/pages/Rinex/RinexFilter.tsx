import { Menu, MenuButton, MenuContent, Modal } from "@componentsReact";

import { useApi, useAuth, useFormReducer, useFormValidation } from "@hooks";
import { getAntennasService, getReceiversService } from "@services";
import {
    AntennaData,
    AntennaServiceData,
    ReceiversData,
    ReceiversServiceData,
} from "@types";
import { isValidNumber } from "@utils/index";

import { RINEX_FILTERS_STATE } from "@utils/reducerFormStates";
import { useEffect, useState } from "react";

interface Props {
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
    handleCloseModal: () => void;
}

const RinexFilter = ({ setStateModal, handleCloseModal }: Props) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const { formState, dispatch } = useFormReducer(RINEX_FILTERS_STATE);
    const quitSpace = (str: string) => str.replace(" ", "_");

    const { fieldValidity, allFieldsValid, validateField } = useFormValidation([
        "completion",
    ]);

    const filters = Object.keys(formState).map((t) => t.replace("_", " "));

    const equipmentFilters = filters.filter(
        (f) => f.includes("receiver") || f.includes("antenna"),
    );

    const dateFilters = filters.filter(
        (f) => f.includes("time") || f.includes("doy") || f.includes("year"),
    );

    const [showMenu, setShowMenu] = useState<
        { type: string; show: boolean } | undefined
    >(undefined);

    const [operatorSelected, setOperatorSelected] = useState<string>("<"); // eslint-disable-line

    const [receivers, setReceivers] = useState<ReceiversData[]>([]);
    const [matchingReceivers, setMatchingReceivers] = useState<ReceiversData[]>(
        [],
    );

    const [antennas, setAntennas] = useState<AntennaData[]>([]);
    const [matchingAntennas, setMatchingAntennas] = useState<AntennaData[]>([]);

    const [loading, setLoading] = useState<boolean>(false);

    const getReceivers = async () => {
        try {
            const res = await getReceiversService<ReceiversServiceData>(api);
            if (res) {
                setReceivers(res.data);
            }
        } catch (error) {
            console.error(error);
        }
    };

    const getAntennas = async () => {
        try {
            const res = await getAntennasService<AntennaServiceData>(api);
            if (res) {
                setAntennas(res.data);
            }
        } catch (err) {
            console.error(err);
        }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { value, name } = e.target;

        if (name === "receiver type") {
            const match = receivers.filter((receiver) =>
                receiver.receiver_code
                    .toLowerCase()
                    .includes(value.toLowerCase()),
            );
            setMatchingReceivers(match);
        }
        if (name === "antenna type") {
            const match = antennas.filter((ant) =>
                ant.antenna_code.toLowerCase().includes(value.toLowerCase()),
            );
            setMatchingAntennas(match);
        }

        dispatch({
            type: "change_value",
            payload: {
                inputName: name.includes(" ") ? quitSpace(name) : name,
                inputValue: value,
            },
        });

        if (name in fieldValidity) {
            validateField(name, value, isValidNumber);
        }
    };

    useEffect(() => {
        const fetchAllData = async () => {
            setLoading(true);
            try {
                await Promise.all([getReceivers(), getAntennas()]);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        };
        fetchAllData();
    }, []);

    //TODO: ADD THE LOGIC TO FILTER THE DATA BASED ON THE FILTERS SELECTED

    // [15:16, 16/10/2024] +1 (901) 900-7324: cambiale el orden, deja arriba YEAR y FYEAR
    // [15:16, 16/10/2024] +1 (901) 900-7324: que DOY quede solo y que Observation time sea como un DESDE HASTA
    // [15:17, 16/10/2024] +1 (901) 900-7324: que en realidad esta compuesto por dos campos
    // [15:17, 16/10/2024] +1 (901) 900-7324: S time > que y E time < que
    // [15:17, 16/10/2024] +1 (901) 900-7324: perdon, >= y <=
    // [15:17, 16/10/2024] +1 (901) 900-7324: BETWEEN para SQL Nerds

    return (
        <Modal
            close={false}
            modalId={"RinexFilters"}
            size={"lg"}
            handleCloseModal={() => handleCloseModal()}
            setModalState={setStateModal}
        >
            <div className="flex flex-col w-full space-y-4">
                <div className="grid grid-cols-2 grid-flow-dense gap-2">
                    <div className="card bg-base-200 grow shadow-xl">
                        <h2 className="card-title border-b-2 border-base-300 p-2">
                            Time Filters
                        </h2>

                        <div className="card-body">
                            <div className="grid grid-cols-2 gap-4">
                                {dateFilters.map((filter, index) => (
                                    <div
                                        key={index}
                                        className="flex flex-col text-sm space-y-2 my-2"
                                    >
                                        <span className="font-bold">
                                            {filter.toUpperCase()}
                                        </span>

                                        <label
                                            htmlFor={filter}
                                            className="input input-bordered flex items-center"
                                        >
                                            <input
                                                type={
                                                    filter.includes("time")
                                                        ? "datetime-local"
                                                        : "text"
                                                }
                                                value={
                                                    formState[
                                                        quitSpace(
                                                            filter,
                                                        ) as keyof typeof formState
                                                    ]
                                                }
                                                name={filter}
                                                id={filter}
                                                className="w-full"
                                                onChange={(e) => {
                                                    handleChange(e);
                                                }}
                                            />
                                        </label>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                    <div className="card bg-base-200 grow shadow-xl ">
                        <h2 className="card-title border-b-2 border-base-300 p-2">
                            Equipment Filters
                        </h2>

                        <div className="card-body">
                            <div className="grid grid-cols-2 gap-4">
                                {equipmentFilters.map((filter, index) => (
                                    <div
                                        key={index}
                                        className="flex flex-col text-sm space-y-2 my-2"
                                    >
                                        <span className="font-bold">
                                            {filter.toUpperCase()}
                                        </span>

                                        <label
                                            htmlFor={filter}
                                            className="input input-bordered flex items-center"
                                        >
                                            <input
                                                type="text"
                                                name={filter}
                                                id={filter}
                                                value={
                                                    formState[
                                                        quitSpace(
                                                            filter,
                                                        ) as keyof typeof formState
                                                    ]
                                                }
                                                disabled={
                                                    filter ===
                                                        "receiver type" ||
                                                    filter === "antenna type"
                                                        ? loading
                                                        : false
                                                }
                                                className="w-full"
                                                onChange={(e) => {
                                                    handleChange(e);
                                                }}
                                            />
                                            {(filter === "receiver type" ||
                                                filter === "antenna type") && (
                                                <MenuButton
                                                    setShowMenu={setShowMenu}
                                                    showMenu={showMenu}
                                                    typeKey={filter}
                                                />
                                            )}
                                        </label>
                                        <div>
                                            {showMenu?.show &&
                                            showMenu.type === filter &&
                                            filter === "receiver type" ? (
                                                <Menu absolute={true}>
                                                    {(matchingReceivers.length >
                                                    0
                                                        ? matchingReceivers
                                                        : receivers
                                                    )?.map((receiver) => (
                                                        <MenuContent
                                                            key={
                                                                receiver.api_id +
                                                                receiver.receiver_code
                                                            }
                                                            typeKey={quitSpace(
                                                                filter,
                                                            )}
                                                            value={
                                                                receiver.receiver_code
                                                            }
                                                            dispatch={dispatch}
                                                            setShowMenu={
                                                                setShowMenu
                                                            }
                                                        />
                                                    ))}
                                                </Menu>
                                            ) : showMenu?.show &&
                                              showMenu.type === filter &&
                                              filter === "antenna type" ? (
                                                <Menu absolute={true}>
                                                    {(matchingAntennas.length >
                                                    0
                                                        ? matchingAntennas
                                                        : antennas
                                                    )?.map((antenna) => (
                                                        <MenuContent
                                                            key={
                                                                antenna.api_id +
                                                                antenna.antenna_code
                                                            }
                                                            typeKey={quitSpace(
                                                                filter,
                                                            )}
                                                            value={
                                                                antenna.antenna_code
                                                            }
                                                            dispatch={dispatch}
                                                            setShowMenu={
                                                                setShowMenu
                                                            }
                                                        />
                                                    ))}
                                                </Menu>
                                            ) : null}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
                <div className="grid grid-cols-1 grid-flow-dense">
                    <div className="card bg-base-200 grow shadow-xl">
                        <h2 className="card-title border-b-2 border-base-300 p-2">
                            Other Filters
                        </h2>
                        <div className="card-body">
                            <div className="grid grid-cols-2 gap-4">
                                {filters.map((filter, index) => {
                                    if (
                                        !dateFilters.includes(filter) &&
                                        !equipmentFilters.includes(filter) &&
                                        filter !== "month" &&
                                        filter !== "day"
                                    ) {
                                        const baseClass =
                                            "input input-bordered flex items-center gap-3 relative";
                                        const additionalClass =
                                            filter in fieldValidity
                                                ? fieldValidity[filter]
                                                    ? ""
                                                    : " input-error"
                                                : "";

                                        return (
                                            <div
                                                key={index}
                                                className="flex flex-col text-sm space-y-2 my-2"
                                            >
                                                <span className="font-bold">
                                                    {filter.toUpperCase()}
                                                </span>

                                                <label
                                                    htmlFor={filter}
                                                    className={`${baseClass}${additionalClass}`}
                                                >
                                                    {filter ===
                                                        "completion" && (
                                                        <select
                                                            defaultValue={"<"}
                                                            className="select select-ghost -ml-4 w-[90px]"
                                                            onChange={(e) => {
                                                                setOperatorSelected(
                                                                    e.target
                                                                        .value,
                                                                );
                                                            }}
                                                        >
                                                            <option disabled>
                                                                Pick operator
                                                            </option>
                                                            <option>
                                                                &lt;
                                                            </option>
                                                            <option>
                                                                &gt;
                                                            </option>
                                                            <option>=</option>
                                                        </select>
                                                    )}
                                                    <input
                                                        type="number"
                                                        min={
                                                            filter ===
                                                            "completion"
                                                                ? 0
                                                                : 0
                                                        }
                                                        max={
                                                            filter ===
                                                            "completion"
                                                                ? 1
                                                                : 100
                                                        }
                                                        step={
                                                            filter ===
                                                            "completion"
                                                                ? 0.01
                                                                : 1
                                                        }
                                                        value={
                                                            formState[
                                                                filter as keyof typeof formState
                                                            ]
                                                        }
                                                        name={filter}
                                                        id={filter}
                                                        className="w-full"
                                                        onChange={(e) => {
                                                            handleChange(e);
                                                        }}
                                                    />
                                                    {filter in fieldValidity ? (
                                                        !fieldValidity[
                                                            filter
                                                        ] ? (
                                                            <span className="badge badge-error right-2 -top-3 absolute z-50">
                                                                completion must
                                                                be greater than
                                                                0
                                                            </span>
                                                        ) : null
                                                    ) : null}
                                                </label>
                                            </div>
                                        );
                                    }
                                })}
                            </div>
                        </div>
                    </div>
                </div>
                <div className="w-full flex flex-grow items-end space-x-4 justify-center">
                    <a
                        className="link link-hover"
                        onClick={() => setStateModal(undefined)}
                    >
                        cancel
                    </a>
                    <button
                        className="btn w-[200px] btn-success"
                        disabled={!allFieldsValid}
                    >
                        apply filters
                    </button>
                </div>
            </div>
        </Modal>
    );
};

export default RinexFilter;
