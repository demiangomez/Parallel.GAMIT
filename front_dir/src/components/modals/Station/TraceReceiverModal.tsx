import {
    Modal,
    Menu,
    MenuContent,
    MenuButton,
    Table,
    Pagination,
} from "@componentsReact";
import useApi from "@hooks/useApi";
import { useAuth } from "@hooks/useAuth";
import {
    getTraceReceiverByRinex,
    getTraceReceiverByStationInfo,
    getReceiversService,
} from "@services";
import { useState, useEffect, useRef } from "react";
import {
    ReceiversData,
    ReceiversServiceData,
    TraceData,
    TraceResponse,
    RinexFilters,
    StationInfoFilters,
} from "@types";

const REGISTERS_PER_PAGE = 5;

const INITIAL_RINEX_FILTERS: RinexFilters = {
    showHeight: true,
    showHeightCode: true,
    showAntennaCode: true,
    showAntennaSerial: true,
    showAntennaRadome: true,
};

const INITIAL_STATION_INFO_FILTERS: StationInfoFilters = {
    showHeight: true,
    showHeightCode: true,
    showAntennaCode: true,
    showAntennaSerial: true,
    showNorth: true,
    showEast: true,
    showAntennaRadome: true,
};

const RINEX_FILTER_CONFIG = [
    { key: "showHeight", label: "Height" },
    { key: "showHeightCode", label: "Height Code" },
    { key: "showAntennaCode", label: "Antenna Code" },
    { key: "showAntennaSerial", label: "Antenna Serial" },
    { key: "showAntennaRadome", label: "Antenna Radome" },
];

const STATION_INFO_FILTER_CONFIG = [
    { key: "showHeight", label: "Height" },
    { key: "showHeightCode", label: "Height Code" },
    { key: "showAntennaCode", label: "Antenna Code" },
    { key: "showAntennaSerial", label: "Antenna Serial" },
    { key: "showNorth", label: "North" },
    { key: "showEast", label: "East" },
    { key: "showAntennaRadome", label: "Antenna Radome" },
];

type Props = {
    closeModal: () => void;
    parentDispatch?: React.Dispatch<any>;
};

const TraceReceiverModal = ({ closeModal, parentDispatch }: Props) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [useRinex, setUseRinex] = useState(true);
    const [receiverType, setReceiverType] = useState("");
    const [receiverCode, setReceiverCode] = useState("");
    const [loading, setLoading] = useState(false);

    const [receivers, setReceivers] = useState<ReceiversData[]>([]);
    const [traceData, setTraceData] = useState<TraceData[]>([]);
    const [matchingReceiverTypes, setMatchingReceiverTypes] = useState<
        string[]
    >([]);

    const [activePage, setActivePage] = useState(1);
    const [pages, setPages] = useState(0);

    const [rinexFilters, setRinexFilters] = useState<RinexFilters>(
        INITIAL_RINEX_FILTERS,
    );
    const [stationInfoFilters, setStationInfoFilters] =
        useState<StationInfoFilters>(INITIAL_STATION_INFO_FILTERS);

    const [showMenu, setShowMenu] = useState<
        { type: string; show: boolean } | undefined
    >(undefined);

    const [searched, setSearched] = useState(false);

    const [msg, setMsg] = useState<
        | {
              status: number;
              msg: string;
              errors?: {
                  errors: { attr: string; code: string; detail?: string }[];
              };
          }
        | undefined
    >(undefined);

    const inputRefReceiverType = useRef<HTMLInputElement>(null);
    const inputRefReceiverCode = useRef<HTMLInputElement>(null);

    // ============ EFECTOS ============
    useEffect(() => {
        fetchReceivers();
    }, []);

    useEffect(() => {
        setActivePage(1);
        setPages(Math.ceil(traceData.length / REGISTERS_PER_PAGE));
    }, [traceData]);

    useEffect(() => {
        if (showMenu) {
            const ref =
                showMenu.type === "receiver_type"
                    ? inputRefReceiverType
                    : inputRefReceiverCode;
            ref?.current?.focus();
        }
    }, [showMenu]);

    // ============ FUNCIONES DE DATOS ============
    const fetchReceivers = async () => {
        try {
            const res = await getReceiversService<ReceiversServiceData>(api);
            if (res?.data) {
                setReceivers(res.data);
            }
        } catch (error) {
            console.error("Error fetching receivers:", error);
        }
    };

    const fetchTraceData = async () => {
        if (!receiverCode.trim()) {
            setMsg({
                status: 400,
                msg: "Validation error",
                errors: {
                    errors: [
                        {
                            attr: "receiver_code",
                            code: "required",
                            detail: "Receiver Serial is required",
                        },
                    ],
                },
            });
            return;
        }
        setMsg(undefined);

        setSearched(true);

        try {
            setLoading(true);
            const serviceCall = useRinex
                ? getTraceReceiverByRinex
                : getTraceReceiverByStationInfo;

            const res = (await serviceCall(
                api,
                receiverCode,
                receiverType,
            )) as TraceResponse;

            if (res?.data && Array.isArray(res.data)) {
                setTraceData(res.data);
                setMsg(undefined);
            } else {
                console.error("Unexpected response structure:", res);
                setTraceData([]);
                setMsg({ status: 500, msg: "Error fetching trace data" });
            }
        } catch (error) {
            console.error("Error fetching trace data:", error);
            setTraceData([]);
        } finally {
            setLoading(false);
        }
    };

    // ============ HANDLERS ============
    const handleInputChange = (
        e:
            | React.ChangeEvent<HTMLInputElement>
            | React.MouseEvent<HTMLInputElement>,
    ) => {
        const target =
            (e as React.ChangeEvent<HTMLInputElement>).target ??
            (e as React.MouseEvent<HTMLInputElement>).target;
        const { value, name } = target as HTMLInputElement;

        if (name === "receiver_type") {
            setReceiverType(value);
            updateReceiverTypeMatches(value);
            setShowMenu({ type: name, show: true });
        } else if (name === "receiver_code") {
            setReceiverCode(value);
        }
    };

    const updateReceiverTypeMatches = (value: string) => {
        const uniqueTypes = [
            ...new Set(receivers.map((r) => r.receiver_code).filter(Boolean)),
        ];
        const matches = uniqueTypes.filter((type) =>
            type.toLowerCase().includes(value.toLowerCase()),
        );
        setMatchingReceiverTypes(matches);
    };

    const handleMenuSelect = (value: string, inputName: string) => {
        if (inputName === "receiver_type") {
            setReceiverType(value);
        }
        setShowMenu(undefined);
    };

    const handleRinexFilterChange = (filterName: keyof RinexFilters) => {
        setRinexFilters((prev) => ({
            ...prev,
            [filterName]: !prev[filterName],
        }));
    };

    const handleStationInfoFilterChange = (
        filterName: keyof StationInfoFilters,
    ) => {
        setStationInfoFilters((prev) => ({
            ...prev,
            [filterName]: !prev[filterName],
        }));
    };

    const handleMethodToggle = (checked: boolean) => {
        setUseRinex(!checked);
    };

    const handleSelectData = (item: TraceData) => {
        if (parentDispatch) {
            const filters = useRinex ? rinexFilters : stationInfoFilters;
            if (filters.showAntennaCode) {
                parentDispatch({
                    type: "change_value",
                    payload: {
                        inputName: "antenna_code",
                        inputValue: useRinex
                            ? item.antenna_type || ""
                            : item.antenna_code || "",
                    },
                });
            }
            if (filters.showAntennaSerial) {
                parentDispatch({
                    type: "change_value",
                    payload: {
                        inputName: "antenna_serial",
                        inputValue: item.antenna_serial || "",
                    },
                });
            }

            if (filters.showHeight) {
                parentDispatch({
                    type: "change_value",
                    payload: {
                        inputName: "antenna_height",
                        inputValue: useRinex
                            ? item.antenna_offset
                            : item.antenna_height,
                    },
                });
            }

            if (filters.showAntennaRadome) {
                parentDispatch({
                    type: "change_value",
                    payload: {
                        inputName: "radome_code",
                        inputValue: useRinex
                            ? item.antenna_dome || ""
                            : item.radome_code || "",
                    },
                });
            }

            if (filters.showHeightCode) {
                parentDispatch({
                    type: "change_value",
                    payload: {
                        inputName: "height_code",
                        inputValue: useRinex
                            ? "DHARP"
                            : item.height_code || "DHARP",
                    },
                });
            }

            if (!useRinex) {
                if (
                    stationInfoFilters.showNorth &&
                    item.antenna_north !== undefined &&
                    item.antenna_north !== null
                ) {
                    parentDispatch({
                        type: "change_value",
                        payload: {
                            inputName: "antenna_north",
                            inputValue: item.antenna_north,
                        },
                    });
                }

                if (
                    stationInfoFilters.showEast &&
                    item.antenna_east !== undefined &&
                    item.antenna_east !== null
                ) {
                    parentDispatch({
                        type: "change_value",
                        payload: {
                            inputName: "antenna_east",
                            inputValue: item.antenna_east,
                        },
                    });
                }
            }

            closeModal();
        }
    };

    // ============ FUNCIONES DE PROCESAMIENTO DE DATOS ============
    const processTableData = () => {
        const paginatedData = traceData.slice(
            REGISTERS_PER_PAGE * (activePage - 1),
            REGISTERS_PER_PAGE * activePage,
        );

        if (paginatedData.length === 0) {
            return {
                titles: [],
                tableData: [],
            };
        }

        const filters = useRinex ? rinexFilters : stationInfoFilters;
        const mappedData = paginatedData.map((item: TraceData) => {
            const mapped: any = {};

            if (useRinex) {
                if (filters.showHeight)
                    mapped.antenna_height = item.antenna_offset;
                if (filters.showHeightCode) mapped.height_code = "DHARP";
                if (filters.showAntennaCode)
                    mapped.antenna_code = item.antenna_type;
                if (filters.showAntennaSerial)
                    mapped.antenna_serial = item.antenna_serial;
                if (filters.showAntennaRadome)
                    mapped.antenna_dome = item.antenna_dome;
            } else {
                if (filters.showHeight)
                    mapped.antenna_height = item.antenna_height;
                if (filters.showHeightCode)
                    mapped.height_code = item.height_code;
                if (filters.showAntennaCode)
                    mapped.antenna_code = item.antenna_code;
                if (filters.showAntennaSerial)
                    mapped.antenna_serial = item.antenna_serial;
                if (filters.showAntennaRadome)
                    mapped.antenna_dome = item.radome_code;

                if (stationInfoFilters.showNorth)
                    mapped.antenna_north = item.antenna_north;
                if (stationInfoFilters.showEast)
                    mapped.antenna_east = item.antenna_east;
            }

            mapped._originalData = item;

            return mapped;
        });

        const titles = Object.keys(mappedData[0] || {}).filter(
            (key) => key !== "_originalData",
        );
        const tableData = mappedData.map((item) => {
            const values = Object.entries(item)
                .filter(([key]) => key !== "_originalData")
                .map(([, value]) => value);
            return [...values, item._originalData];
        });

        return { titles, tableData };
    };

    const getUniqueReceiverTypes = () => {
        return [
            ...new Set(receivers.map((r) => r.receiver_code).filter(Boolean)),
        ];
    };

    // ============ COMPONENTES DE RENDERIZADO ============
    const renderMethodToggle = () => (
        <div className="flex items-center gap-3 mb-3">
            <span
                className={`text-sm ${useRinex ? "font-semibold" : "text-gray-500"}`}
            >
                By Rinex
            </span>
            <label className="cursor-pointer">
                <input
                    type="checkbox"
                    checked={!useRinex}
                    onChange={(e) => handleMethodToggle(e.target.checked)}
                    className="toggle"
                />
            </label>
            <span
                className={`text-sm ${!useRinex ? "font-semibold" : "text-gray-500"}`}
            >
                By Station Info
            </span>
        </div>
    );

    const renderFilterCheckbox = (
        config: any,
        isChecked: boolean,
        onChange: () => void,
    ) => (
        <label
            key={config.key}
            className="flex items-center gap-2 cursor-pointer"
        >
            <input
                type="checkbox"
                checked={isChecked}
                onChange={onChange}
                className="checkbox"
            />
            <span className="text-xs text-gray-700">{config.label}</span>
        </label>
    );

    const renderFilters = () => {
        const isRinexMode = useRinex;
        const config = isRinexMode
            ? RINEX_FILTER_CONFIG
            : STATION_INFO_FILTER_CONFIG;
        const filters = isRinexMode ? rinexFilters : stationInfoFilters;
        const handleChange = isRinexMode
            ? handleRinexFilterChange
            : handleStationInfoFilterChange;

        return (
            <div className="bg-base-200 p-3 rounded-lg mb-3">
                <h4 className="text-sm font-medium mb-2 text-gray-700">
                    Select data to display:
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {config.map((item) => {
                        const isChecked =
                            filters[item.key as keyof typeof filters];
                        const onChange = () => handleChange(item.key as any);
                        return renderFilterCheckbox(item, isChecked, onChange);
                    })}
                </div>
            </div>
        );
    };

    const renderReceiverTypeInput = () => {
        const menuOptions =
            matchingReceiverTypes.length > 0
                ? matchingReceiverTypes
                : getUniqueReceiverTypes();

        return (
            <div className="form-control">
                <label className="label py-0">
                    <span className="label-text text-xs font-medium">
                        Receiver Type (optional)
                    </span>
                </label>
                <div className="relative">
                    <div className="flex">
                        <input
                            id="receiverType"
                            ref={inputRefReceiverType}
                            type="text"
                            name="receiver_type"
                            value={receiverType}
                            onChange={handleInputChange}
                            onClick={handleInputChange}
                            placeholder="Enter receiver type"
                            className="input input-bordered w-full flex-1"
                            autoComplete="off"
                        />
                        <MenuButton
                            setShowMenu={setShowMenu}
                            showMenu={showMenu}
                            typeKey="receiver_type"
                        />
                    </div>
                    {showMenu?.show && showMenu.type === "receiver_type" && (
                        <Menu>
                            {menuOptions.map((type, index) => (
                                <MenuContent
                                    key={`${type}-${index}`}
                                    typeKey="receiver_type"
                                    value={type}
                                    dispatch={(action: any) => {
                                        if (action.type === "change_value") {
                                            handleMenuSelect(
                                                action.payload.inputValue,
                                                action.payload.inputName,
                                            );
                                        }
                                    }}
                                    setShowMenu={setShowMenu}
                                />
                            ))}
                        </Menu>
                    )}
                </div>
            </div>
        );
    };

    const renderReceiverCodeInput = () => {
        const errorBadge = msg?.errors?.errors?.find(
            (err) => err.attr === "receiver_code",
        );

        return (
            <div className="form-control">
                <label className="label py-0">
                    <span className="label-text text-xs font-medium">
                        Receiver Serial *
                    </span>
                </label>
                <label
                    id="receiverCode"
                    className={`w-full input input-bordered flex items-center gap-2 ${errorBadge ? "input-error" : ""}`}
                    title={errorBadge ? errorBadge.detail : ""}
                >
                    <input
                        ref={inputRefReceiverCode}
                        type="text"
                        name="receiver_code"
                        value={receiverCode}
                        onChange={handleInputChange}
                        placeholder="Enter receiver serial"
                        className="grow bg-transparent outline-none"
                        autoComplete="off"
                    />
                    {errorBadge && (
                        <span className="badge badge-error">
                            {errorBadge.code}
                        </span>
                    )}
                </label>
            </div>
        );
    };

    const renderActionButton = () => (
        <div className="flex justify-center mt-4">
            <button
                type="button"
                onClick={fetchTraceData}
                className="btn btn-md"
                disabled={loading}
            >
                {loading ? (
                    <>
                        <span className="loading loading-spinner loading-xs"></span>
                        Loading...
                    </>
                ) : (
                    `Get Trace by ${useRinex ? "Rinex" : "Station Info"}`
                )}
            </button>
        </div>
    );

    const renderResults = () => {
        const hasData = traceData.length > 0;
        const { titles, tableData } = processTableData();

        if (!hasData && !searched) {
            return null;
        }

        if (!hasData && searched) {
            return (
                <div className="mt-4 text-center">
                    <div className="divider text-sm font-semibold">Results</div>
                    <p className="text-sm text-gray-600">No data found.</p>
                </div>
            );
        }

        const bodyWithoutObject = tableData.map((row) => row.slice(0, -1));

        const findOriginalFromRow = (rowWithoutOriginal: any[]) => {
            const found = tableData.find((r) => {
                try {
                    return (
                        JSON.stringify(r.slice(0, -1)) ===
                        JSON.stringify(rowWithoutOriginal)
                    );
                } catch {
                    return false;
                }
            });
            return found ? found[found.length - 1] : undefined;
        };

        return (
            <div className="mt-4">
                <div className="divider text-sm font-semibold">Results</div>
                <div className="overflow-x-auto">
                    <Table
                        titles={[parentDispatch ? "Select" : "", ...titles]}
                        body={bodyWithoutObject}
                        loading={loading}
                        table="TraceReceiver"
                        dataOnly={true}
                        onClickFunction={() => {}}
                        selectAction={
                            parentDispatch
                                ? (data) => {
                                      const originalData = findOriginalFromRow(
                                          data as any[],
                                      );
                                      if (originalData) {
                                          handleSelectData(originalData);
                                      }
                                  }
                                : undefined
                        }
                    />
                </div>
                {pages > 1 && (
                    <div className="flex justify-center mt-2">
                        <Pagination
                            pages={pages}
                            pagesToShow={2}
                            activePage={activePage}
                            handlePage={setActivePage}
                        />
                    </div>
                )}
            </div>
        );
    };

    // ============ RENDER PRINCIPAL ============
    return (
        <Modal
            close={true}
            size="xl"
            modalId="TraceReceiverModal"
            handleCloseModal={() => {
                closeModal();
            }}
        >
            <div className="p-4">
                <h3 className="font-bold text-center text-xl mb-4">
                    Trace Receiver
                </h3>

                <div className="card bg-base-100 shadow-sm">
                    <div className="card-body p-4">
                        {renderMethodToggle()}
                        {renderFilters()}

                        <div className="grid grid-cols-2 gap-3 mt-2">
                            {renderReceiverTypeInput()}
                            {renderReceiverCodeInput()}
                        </div>

                        {renderActionButton()}
                    </div>
                </div>

                {renderResults()}
            </div>
        </Modal>
    );
};

export default TraceReceiverModal;
