import { useEffect, useState } from "react";
import { Menu, MenuButton, MenuContent, Modal } from "@componentsReact";

import { useApi, useAuth, useFormReducer, useFormValidation } from "@hooks";
import {
    getAntennasService,
    getReceiversService,
    getRinexWithStatusService,
} from "@services";
import {
    AntennaData,
    AntennaServiceData,
    GetParams,
    ReceiversData,
    ReceiversServiceData,
    RinexObject,
} from "@types";

import { isValidNumber } from "@utils";
import { RINEX_FILTERS_STATE } from "@utils/reducerFormStates";

interface Props {
    stationApiId: number | undefined;
    registersPerPage: number;
    filters: Record<keyof typeof RINEX_FILTERS_STATE, any>;
    setFilters: React.Dispatch<
        React.SetStateAction<Record<keyof typeof RINEX_FILTERS_STATE, any>>
    >;
    setPages: React.Dispatch<React.SetStateAction<number>>;
    setProblematicRinex: React.Dispatch<
        React.SetStateAction<RinexObject[] | undefined>
    >;
    setRinex: React.Dispatch<React.SetStateAction<RinexObject[] | undefined>>;
    setRinexFilter: React.Dispatch<React.SetStateAction<boolean>>;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
    calculateTotalLength: (rinexs: RinexObject[]) => number;
    handleCloseModal: () => void;
}

const RinexFilter = ({
    stationApiId,
    registersPerPage,
    filters,
    setFilters,
    setPages,
    setProblematicRinex,
    setRinex,
    setRinexFilter,
    setStateModal,
    calculateTotalLength,
    handleCloseModal,
}: Props) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const { formState, dispatch } = useFormReducer(RINEX_FILTERS_STATE);
    const quitSpace = (str: string) => str.replace(" ", "_");

    const { fieldValidity, allFieldsValid, validateField } = useFormValidation([
        "completion",
    ]);

    const formStatefilters = Object.keys(formState).map((t) =>
        t.replace("_", " "),
    );

    const equipmentFilters = formStatefilters.filter(
        (f) => f.includes("receiver") || f.includes("antenna"),
    );

    const dateFilters = formStatefilters.filter(
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

    const formatDateTime = (dateTime: string): string => {
        const [date, time] = dateTime.split("T");
        if (!date || !time) return "";
        return `${date} ${time}`;
    };

    const getRinexFiltered = async () => {
        try {
            const params: GetParams = {
                observation_doy: formState.doy,
                observation_f_year: formState["f_year"],
                observation_s_time_since: formatDateTime(
                    formState["s_time"] ?? "",
                ),
                observation_e_time_until: formatDateTime(
                    formState["e_time"] ?? "",
                ),
                observation_year: formState.year,
                antenna_dome: formState["antenna_dome"],
                antenna_offset: formState["antenna_offset"],
                antenna_serial: formState["antenna_serial"],
                antenna_type: formState["antenna_type"],
                receiver_fw: formState["receiver_fw"],
                receiver_serial: formState["receiver_serial"],
                receiver_type: formState["receiver_type"],
                completion_operator:
                    operatorSelected === "<"
                        ? "LESS_THAN"
                        : operatorSelected === ">"
                          ? "GREATER_THAN"
                          : "EQUAL",
                completion: formState.completion,
                interval: formState.interval,
                offset: 0,
                limit: registersPerPage,
            };

            Object.keys(params).forEach((key) => {
                if (
                    params[key as keyof GetParams] === undefined ||
                    params[key as keyof GetParams] === ""
                ) {
                    delete params[key as keyof GetParams];
                }
            });

            setLoading(true);
            const res = await getRinexWithStatusService<RinexObject[]>(
                api,
                stationApiId ?? 0,
                params,
            );
            const rinexWithGroupId = res
                .map((item, index) => {
                    return {
                        ...item,
                        rinex: item.rinex
                            .map((r) => ({
                                ...r,
                                rinex: r.rinex.filter((r2) => !r2.filtered),
                            }))
                            .filter((r) => r.rinex.length > 0),
                        groupId: `group-${index}`,
                    };
                })
                .filter((item) => item.rinex.length > 0);

            setRinex(rinexWithGroupId);

            const problematic = rinexWithGroupId
                .filter((rinex) =>
                    rinex.rinex.some((r) =>
                        r.rinex.some((r2) => !r2.has_station_info),
                    ),
                )
                .map((rinex) => ({
                    ...rinex,
                    rinex: rinex.rinex
                        .map((r) => ({
                            ...r,
                            rinex: r.rinex.filter((r2) => !r2.has_station_info),
                        }))
                        .filter((r) => r.rinex.length > 0),
                }))
                .filter((rinex) => rinex.rinex.length > 0);

            setProblematicRinex(problematic);
            setPages(Math.ceil(calculateTotalLength(res) / registersPerPage));
            setRinexFilter(true);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
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

        setFilters((prev) => ({
            ...prev,
            [name.includes(" ") ? quitSpace(name) : name]: value,
        }));
    };

    const handleSubmitForm = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        getRinexFiltered();
    };

    useEffect(() => {
        if (Object.values(filters).some((r) => r.length > 0)) {
            dispatch({
                type: "set",
                payload: filters,
            });
        }
    }, [filters]);

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

    return (
        <Modal
            close={false}
            modalId={"RinexFilters"}
            size={"lg"}
            handleCloseModal={() => handleCloseModal()}
            setModalState={setStateModal}
        >
            <form
                className="flex flex-col w-full space-y-4"
                onSubmit={handleSubmitForm}
            >
                <div className="grid grid-cols-2 grid-flow-dense gap-2">
                    <div className="card bg-base-200 grow shadow-xl">
                        <h2 className="card-title border-b-2 border-base-300 p-2">
                            Time Filters
                        </h2>

                        <div className="card-body">
                            <div className="grid grid-cols-1 gap-4">
                                <div className="flex flex-col text-sm space-y-2 my-2">
                                    <span className="font-bold">F YEAR</span>
                                    <label
                                        htmlFor="f year"
                                        className="input input-bordered flex items-center w-full"
                                    >
                                        <input
                                            type="text"
                                            value={
                                                formState[
                                                    quitSpace(
                                                        "f year",
                                                    ) as keyof typeof formState
                                                ]
                                            }
                                            name="f year"
                                            id="f year"
                                            className="w-full"
                                            onChange={(e) => {
                                                handleChange(e);
                                            }}
                                        />
                                    </label>
                                </div>
                                <div className="flex flex-col text-sm space-y-2 my-2">
                                    <span className="font-bold">YEAR</span>
                                    <label
                                        htmlFor="year"
                                        className="input input-bordered flex items-center w-full"
                                    >
                                        <input
                                            type="text"
                                            value={
                                                formState[
                                                    quitSpace(
                                                        "year",
                                                    ) as keyof typeof formState
                                                ]
                                            }
                                            name="year"
                                            id="year"
                                            className="w-full"
                                            onChange={(e) => {
                                                handleChange(e);
                                            }}
                                        />
                                    </label>
                                </div>
                                <div className="flex flex-col text-sm space-y-2 my-2 overflow-x-auto">
                                    <span className="font-bold">
                                        OBSERVATION TIME
                                    </span>
                                    <div className="join">
                                        <label
                                            htmlFor="s time"
                                            className="input join-item input-bordered flex items-center w-full"
                                        >
                                            <input
                                                type="datetime-local"
                                                value={
                                                    formState[
                                                        quitSpace(
                                                            "s time",
                                                        ) as keyof typeof formState
                                                    ]
                                                }
                                                name="s time"
                                                id="s time"
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
                                            htmlFor="e time"
                                            className="input join-item input-bordered flex items-center w-full"
                                        >
                                            <input
                                                type="datetime-local"
                                                value={
                                                    formState[
                                                        quitSpace(
                                                            "e time",
                                                        ) as keyof typeof formState
                                                    ]
                                                }
                                                name="e time"
                                                id="e time"
                                                className="w-full"
                                                onChange={(e) => {
                                                    handleChange(e);
                                                }}
                                            />
                                        </label>
                                    </div>
                                </div>
                                <div className="flex flex-col text-sm space-y-2 my-2">
                                    <span className="font-bold">DOY</span>
                                    <label
                                        htmlFor="doy"
                                        className="input input-bordered flex items-center w-full"
                                    >
                                        <input
                                            type="text"
                                            value={
                                                formState[
                                                    quitSpace(
                                                        "doy",
                                                    ) as keyof typeof formState
                                                ]
                                            }
                                            name="doy"
                                            id="doy"
                                            className="w-full"
                                            onChange={(e) => {
                                                handleChange(e);
                                            }}
                                        />
                                    </label>
                                </div>
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
                                {formStatefilters.map((filter, index) => {
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
                                                                ? 0.001
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
                    <button
                        className="btn w-[200px] btn-success"
                        type="submit"
                        disabled={!allFieldsValid}
                    >
                        apply filters
                    </button>

                    <a
                        className="link link-hover"
                        onClick={() => {
                            setStateModal(undefined);
                            setRinexFilter(false);
                            setRinex(undefined);
                            setFilters(RINEX_FILTERS_STATE);
                        }}
                    >
                        clean filters
                    </a>
                </div>
            </form>
        </Modal>
    );
};

export default RinexFilter;
