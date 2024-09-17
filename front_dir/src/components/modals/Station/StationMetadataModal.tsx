import { useEffect, useMemo, useState } from "react";

import {
    Alert,
    ConfirmDeleteModal,
    LargeSkeleton,
    Menu,
    MenuButton,
    MenuContent,
    Modal,
    StationAddFileModal,
} from "@componentsReact";

import useApi from "@hooks/useApi";
import { useAuth } from "@hooks/useAuth";
import UseFormReducer from "@hooks/useFormReducer";

import {
    ArrowDownTrayIcon,
    ClipboardDocumentIcon,
    PencilSquareIcon,
    PlusCircleIcon,
    TrashIcon,
} from "@heroicons/react/24/outline";

import defPhoto from "@assets/images/placeholder.png";

import {
    delStationsFilesAttachedService,
    getMonumentsTypesService,
    getRinexService,
    getStationInfoService,
    getStationsFilesAttachedService,
    getStationStatusService,
    getStationTypesService,
    patchStationMetaService,
    patchStationService,
} from "@services";

import { decimalToDMS, formattedDates, showModal } from "@utils";

import {
    ErrorResponse,
    Errors,
    ExtendedStationData,
    MonumentTypes,
    MonumentTypesServiceData,
    RinexData,
    RinexServiceData,
    StationData,
    StationFilesData,
    StationFilesServiceData,
    StationInfoData,
    StationInfoServiceData,
    StationMetadataServiceData,
    StationStatus,
    StationStatusServiceData,
} from "@types";

interface StationMetadataProps {
    close: boolean;
    size?: "sm" | "md" | "lg" | "xl" | "fit";
    station?: StationData | undefined;
    stationMeta: StationMetadataServiceData | undefined;
    refetchStationMeta?: () => void;
    refetch: () => void;
    setModalState: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
}

const StationMetadataModal = ({
    close,
    station,
    stationMeta,
    size,
    refetchStationMeta,
    refetch,
    setModalState,
}: StationMetadataProps) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [metaMsg, setMetaMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);
    const [stationMsg, setStationMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [fileMsg, setFileMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [showMenu, setShowMenu] = useState<
        { type: string; show: boolean } | undefined
    >(undefined);

    const [loading, setLoading] = useState<boolean>(false);
    const [updateLoading, setUpdateLoading] = useState<boolean>(false);
    const [edit, setEdit] = useState<boolean>(false);

    const [monumentType, setMonumentType] = useState<MonumentTypes[]>([]);
    const [matchingMonuments, setMatchingMonuments] = useState<MonumentTypes[]>(
        [],
    );

    const [stationStatus, setStationStatus] = useState<StationStatus[]>([]);
    const [matchingStatus, setMatchingStatus] = useState<StationStatus[]>([]);

    const [stationType, setStationType] = useState<StationStatus[]>([]);
    const [matchingTypes, setMatchingTypes] = useState<StationStatus[]>([]);

    const [firstRinex, setFirstRinex] = useState<RinexData | undefined>(
        undefined,
    );
    const [lastRinex, setLastRinex] = useState<RinexData | undefined>(
        undefined,
    );

    const [stationInfo, setStationInfo] = useState<StationInfoData | undefined>(
        undefined,
    );

    const [fileType, setFileType] = useState<"meta" | "none">("none");

    const [files, setFiles] = useState<StationFilesData[] | undefined>(
        undefined,
    );

    const [fileToDel, setFileToDel] = useState<number | undefined>(undefined);

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const getTypes = async () => {
        try {
            setLoading(true);
            if (stationMeta) {
                const status =
                    await getStationStatusService<StationStatusServiceData>(
                        api,
                    );

                const types =
                    await getStationTypesService<StationStatusServiceData>(api);

                const monuments =
                    await getMonumentsTypesService<MonumentTypesServiceData>(
                        api,
                    );

                setStationType(types.data ?? []);
                setMonumentType(monuments.data ?? []);
                setStationStatus(status.data ?? []);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const getRinex = async () => {
        try {
            setLoading(true);
            const firstRes = await getRinexService<RinexServiceData>(api, {
                network_code: station?.network_code,
                station_code: station?.station_code,
                limit: 1,
                offset: 0,
            });
            const totalRecords = firstRes.total_count;
            const lastRes = await getRinexService<RinexServiceData>(api, {
                network_code: station?.network_code,
                station_code: station?.station_code,
                limit: 1,
                offset: totalRecords - 1,
            });
            setFirstRinex(firstRes.data[0]);
            setLastRinex(lastRes.data[0]);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const getStationInfo = async () => {
        try {
            setLoading(true);
            if (stationMeta && station) {
                const res = await getStationInfoService<StationInfoServiceData>(
                    api,
                    {
                        network_code: station?.network_code ?? "",
                        station_code: station?.station_code ?? "",
                        offset: 0,
                        limit: 0,
                    },
                );

                setStationInfo(
                    res.data.sort(
                        (a, b) =>
                            new Date(b.date_end).getTime() -
                            new Date(a.date_end).getTime(),
                    )[0],
                );
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const stationId = stationMeta?.station ?? undefined;

    const getFiles = async () => {
        try {
            setLoading(true);
            if (stationId) {
                const res =
                    await getStationsFilesAttachedService<StationFilesServiceData>(
                        api,
                        { station_api_id: stationId, offset: 0, limit: 0 },
                    );
                setFiles(res.data);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const delFile = async (id: number | undefined) => {
        try {
            setLoading(true);
            if (stationId && typeof id === "number") {
                const res =
                    await delStationsFilesAttachedService<ErrorResponse>(
                        api,
                        id,
                    );

                if ("status" in res && res.status !== "success") {
                    setFileMsg({
                        status: res.statusCode,
                        msg: res.response.type,
                        errors: res.response,
                    });
                } else {
                    setFileMsg({
                        status: res.statusCode,
                        msg: "File deleted successfully",
                    });
                    getFiles();
                }
            } else {
                setFileMsg({
                    status: 400,
                    msg: "File not found",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const delFileMeta = async () => {
        try {
            setLoading(true);
            if (stationId) {
                const formData = new FormData();

                formData.append("navigation_file_delete", "true");
                formData.append("station", String(stationId));

                const res = await patchStationMetaService<
                    StationFilesData | ErrorResponse
                >(api, Number(stationMeta?.station), formData);
                if (res.statusCode !== 200 && "status" in res) {
                    setFileMsg({
                        status: res.statusCode,
                        msg: res.response.type,
                        errors: res.response,
                    });
                } else if (res.statusCode === 200) {
                    setFileMsg({
                        status: res.statusCode,
                        msg: "File deleted successfully",
                    });
                    refetchStationMeta && refetchStationMeta();
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        getFiles();
    }, [stationId]);

    useEffect(() => {
        getTypes();
        getRinex();
        getStationInfo();
    }, [stationMeta]);

    const formattedData = useMemo(() => {
        return {
            equipment: {
                antenna_code: stationInfo?.antenna_code,
                antenna_serial: stationInfo?.antenna_serial,
                height_code: stationInfo?.height_code,
                receiver_code: stationInfo?.receiver_code,
                receiver_serial: stationInfo?.receiver_serial,
                receiver_version: stationInfo?.receiver_vers,
                radome_code: stationInfo?.radome_code,
            },
            rinex: {
                first_rinex: firstRinex?.observation_e_time ?? "",
                last_rinex: lastRinex?.observation_e_time ?? "",
                comments: stationMeta?.comments ?? "",
                navigation_file: stationMeta?.navigation_filename ?? "",
            },
            booleans: {
                has_battery: stationMeta?.has_battery ?? false,
                has_communications: stationMeta?.has_communications ?? false,
            },
            booleansDesc: {
                battery_description: stationMeta?.battery_description ?? "",
                communications_description:
                    stationMeta?.communications_description ?? "",
            },
            stationMeta: {
                station_type:
                    stationType.find(
                        (st) => st.id === Number(stationMeta?.station_type),
                    )?.name ?? "",
                monument_type:
                    monumentType.find(
                        (mt) => mt.id === Number(stationMeta?.monument_type),
                    )?.name ?? "",
                status:
                    stationStatus.find(
                        (st) => st.id === Number(stationMeta?.status),
                    )?.name ?? "",
                remote_access_link: stationMeta?.remote_access_link ?? "",
            },
            station: {
                lat: String(station?.lat) ?? "",
                lon: String(station?.lon) ?? "",
                height: String(station?.height) ?? "",
                auto_x: String(station?.auto_x) ?? "",
                auto_y: String(station?.auto_y) ?? "",
                auto_z: String(station?.auto_z) ?? "",
            },
        };
    }, [stationType, monumentType, stationStatus]);

    const { formState, dispatch } = UseFormReducer(formattedData);

    useEffect(() => {
        dispatch({
            type: "set",
            payload: formattedData,
        });
    }, [formattedData]);

    const handleChange = (
        e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
    ) => {
        const { value, name } = e.target;
        dispatch({
            type: "change_value",
            payload: {
                inputName: name,
                inputValue: value,
            },
        });
        if (name === "stationMeta.monument_type") {
            const match = monumentType?.filter((mt) =>
                mt.name.toLowerCase().includes(value.toLowerCase()),
            );
            setMatchingMonuments(match);
        }
        if (name === "stationMeta.status") {
            const match = stationStatus?.filter((st) =>
                st.name.toLowerCase().includes(value.toLowerCase()),
            );
            setMatchingStatus(match);
        }
        if (name === "stationMeta.station_type") {
            const match = stationType?.filter((st) =>
                st.name.toLowerCase().includes(value.toLowerCase()),
            );
            setMatchingTypes(match);
        }
    };

    const updateMetadata = async () => {
        try {
            if (station && stationMeta) {
                setUpdateLoading(true);

                const meta = {
                    has_battery: formState.booleans.has_battery,
                    has_communications: formState.booleans.has_communications,
                    comments: formState.rinex.comments,
                    remote_access_link:
                        formState.stationMeta.remote_access_link,
                    battery_description:
                        formState.booleansDesc.battery_description,
                    communications_description:
                        formState.booleansDesc.communications_description,
                    station_type: stationType.find(
                        (st) => st.name === formState.stationMeta.station_type,
                    )?.id,
                    monument_type: monumentType.find(
                        (mt) => mt.name === formState.stationMeta.monument_type,
                    )?.id,
                    status: stationStatus.find(
                        (st) => st.name === formState.stationMeta.status,
                    )?.id,
                    navigation_file_delete: false,
                    station: stationId,
                };

                const formData = new FormData();

                Object.entries(meta).forEach(([key, value]) => {
                    if (value) {
                        formData.append(key, String(value));
                    }
                });

                const resMeta = await patchStationMetaService<
                    StationMetadataServiceData | ErrorResponse
                >(api, Number(stationMeta?.station), meta);
                if ("msg" in resMeta) {
                    setMetaMsg({
                        status: resMeta.statusCode,
                        msg: resMeta.response.type,
                        errors: resMeta.response,
                    });
                } else {
                    setMetaMsg({
                        status: Number(resMeta.statusCode),
                        msg: "Metadata updated successfully",
                    });
                }
                const res = await patchStationService<
                    ExtendedStationData | ErrorResponse
                >(api, Number(station?.api_id), formState.station);
                if (res.statusCode !== 200 && "status" in res) {
                    setStationMsg({
                        status: res.statusCode,
                        msg: res.msg,
                        errors: res.response,
                    });
                } else if (res.statusCode === 200) {
                    setStationMsg({
                        status: Number(res.statusCode),
                        msg: "Station updated successfully",
                    });
                }

                if (resMeta.statusCode === 200 && res.statusCode === 200) {
                    setTimeout(() => {
                        setEdit(false);
                    }, 1000);
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setUpdateLoading(false);
        }
    };

    const generalFields = [
        "Station Type",
        "Monument",
        "Status",
        "Remote Access Link",
    ];
    const generalFields2 = ["Battery", "Communications"];
    const generalFields3 = [
        "First rinex",
        "Last rinex",
        "Comments",
        "Navigation File",
    ];
    const equipmentFields = [
        "Antenna Code",
        "Antenna Serial",
        "Height Code",
        "Receiver Code",
        "Receiver Serial",
        "Receiver Version",
        "Radome Code",
    ];

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    return (
        <Modal
            close={close}
            modalId={"Metadata"}
            size={size}
            setModalState={setModalState}
            handleCloseModal={() => {
                refetch();
            }}
        >
            <div className="w-full inline-flex">
                <h3 className="font-bold text-center text-3xl my-2 grow">
                    Metadata
                </h3>
                <button
                    className="flex items-center btn btn-ghost btn-circle"
                    onClick={() => setEdit(!edit)}
                >
                    <PencilSquareIcon title="edit" className="size-8" />
                </button>
            </div>
            {loading ? (
                <LargeSkeleton />
            ) : (
                <div className="space-y-4">
                    <div className="grid grid-cols-2 space-y-4 grid-flow-dense">
                        <div className="card bg-base-200 grow shadow-xl mr-4">
                            <h2 className="card-title border-b-2 border-base-300 p-2">
                                General
                            </h2>

                            <div className="card-body">
                                <div className="grid grid-cols-2 gap-6">
                                    {Object.keys(formState.stationMeta).map(
                                        (key, idx) => {
                                            if (key) {
                                                const errorBadge =
                                                    metaMsg?.errors?.errors?.find(
                                                        (error) =>
                                                            error.attr === key,
                                                    );

                                                return (
                                                    <div key={idx}>
                                                        <div className="text-sm font-bold flex items-center">
                                                            {generalFields[idx]}{" "}
                                                            <div
                                                                className={`size-3  rounded-full ml-3`}
                                                                title={
                                                                    generalFields[
                                                                        idx
                                                                    ]
                                                                }
                                                            ></div>
                                                        </div>
                                                        {edit ? (
                                                            <div className="flex flex-col space-y-1">
                                                                <label
                                                                    className={`input input-bordered flex items-center  ${errorBadge ? "input-error" : ""}  `}
                                                                    title={
                                                                        errorBadge
                                                                            ? errorBadge.detail
                                                                            : ""
                                                                    }
                                                                >
                                                                    <input
                                                                        className="w-full"
                                                                        autoComplete="off"
                                                                        type="text"
                                                                        value={
                                                                            formState
                                                                                .stationMeta[
                                                                                key as keyof typeof formState.stationMeta
                                                                            ] ??
                                                                            ""
                                                                        }
                                                                        name={
                                                                            "stationMeta." +
                                                                            key
                                                                        }
                                                                        onChange={(
                                                                            e,
                                                                        ) =>
                                                                            handleChange(
                                                                                e,
                                                                            )
                                                                        }
                                                                    />
                                                                    {errorBadge && (
                                                                        <span className="badge badge-error self-start -mt-2">
                                                                            {
                                                                                errorBadge.code
                                                                            }
                                                                        </span>
                                                                    )}
                                                                    {(key ===
                                                                        "station_type" ||
                                                                        key ===
                                                                            "monument_type" ||
                                                                        key ===
                                                                            "status") && (
                                                                        <MenuButton
                                                                            setShowMenu={
                                                                                setShowMenu
                                                                            }
                                                                            showMenu={
                                                                                showMenu
                                                                            }
                                                                            typeKey={
                                                                                key
                                                                            }
                                                                        />
                                                                    )}
                                                                </label>
                                                            </div>
                                                        ) : key ===
                                                          "remote_access_link" ? (
                                                            <a
                                                                target="_blank"
                                                                className="link link-hover break-words"
                                                                href={
                                                                    formState
                                                                        .stationMeta[
                                                                        key as keyof typeof formState.stationMeta
                                                                    ]
                                                                }
                                                            >
                                                                {
                                                                    formState
                                                                        .stationMeta[
                                                                        key as keyof typeof formState.stationMeta
                                                                    ]
                                                                }
                                                            </a>
                                                        ) : (
                                                            <p className="break-words">
                                                                {formState
                                                                    .stationMeta[
                                                                    key as keyof typeof formState.stationMeta
                                                                ] &&
                                                                formState
                                                                    .stationMeta[
                                                                    key as keyof typeof formState.stationMeta
                                                                ] !== "" ? (
                                                                    formState
                                                                        .stationMeta[
                                                                        key as keyof typeof formState.stationMeta
                                                                    ]
                                                                ) : (
                                                                    <span className="text-gray-400">
                                                                        No info
                                                                    </span>
                                                                )}
                                                            </p>
                                                        )}
                                                        {showMenu?.show &&
                                                        showMenu.type === key &&
                                                        key ===
                                                            "monument_type" ? (
                                                            <Menu
                                                                absolute={true}
                                                            >
                                                                {(matchingMonuments.length >
                                                                0
                                                                    ? matchingMonuments
                                                                    : monumentType
                                                                )?.map((mt) => (
                                                                    <MenuContent
                                                                        key={
                                                                            mt.id
                                                                        }
                                                                        typeKey={
                                                                            "stationMeta." +
                                                                            key
                                                                        }
                                                                        value={
                                                                            mt.name
                                                                        }
                                                                        dispatch={
                                                                            dispatch
                                                                        }
                                                                        setShowMenu={
                                                                            setShowMenu
                                                                        }
                                                                    />
                                                                ))}
                                                            </Menu>
                                                        ) : showMenu?.show &&
                                                          showMenu.type ===
                                                              key &&
                                                          key ===
                                                              "station_type" ? (
                                                            <Menu
                                                                absolute={true}
                                                            >
                                                                {(matchingTypes.length >
                                                                0
                                                                    ? matchingTypes
                                                                    : stationType
                                                                )?.map((st) => (
                                                                    <MenuContent
                                                                        key={
                                                                            st.id
                                                                        }
                                                                        typeKey={
                                                                            "stationMeta." +
                                                                            key
                                                                        }
                                                                        value={
                                                                            st.name
                                                                        }
                                                                        dispatch={
                                                                            dispatch
                                                                        }
                                                                        setShowMenu={
                                                                            setShowMenu
                                                                        }
                                                                    />
                                                                ))}
                                                            </Menu>
                                                        ) : (
                                                            showMenu?.show &&
                                                            showMenu.type ===
                                                                key &&
                                                            key ===
                                                                "status" && (
                                                                <Menu
                                                                    absolute={
                                                                        true
                                                                    }
                                                                >
                                                                    {(matchingStatus.length >
                                                                    0
                                                                        ? matchingStatus
                                                                        : stationStatus
                                                                    )?.map(
                                                                        (
                                                                            st,
                                                                        ) => (
                                                                            <MenuContent
                                                                                key={
                                                                                    st.id
                                                                                }
                                                                                typeKey={
                                                                                    "stationMeta." +
                                                                                    key
                                                                                }
                                                                                value={
                                                                                    st.name
                                                                                }
                                                                                dispatch={
                                                                                    dispatch
                                                                                }
                                                                                setShowMenu={
                                                                                    setShowMenu
                                                                                }
                                                                            />
                                                                        ),
                                                                    )}
                                                                </Menu>
                                                            )
                                                        )}
                                                    </div>
                                                );
                                            }
                                        },
                                    )}
                                    {Object.entries(formState.booleans).map(
                                        ([key, value], idx) => {
                                            if (key) {
                                                const pointer = value
                                                    ? "bg-green-500"
                                                    : "bg-red-500";

                                                const descKey =
                                                    key === "has_battery"
                                                        ? "battery_description"
                                                        : "communications_description";

                                                const errorBadge =
                                                    metaMsg?.errors?.errors?.find(
                                                        (error) =>
                                                            error.attr ===
                                                            descKey,
                                                    );

                                                return (
                                                    <div key={idx}>
                                                        <div className="text-sm font-bold flex items-center">
                                                            {
                                                                generalFields2[
                                                                    idx
                                                                ]
                                                            }
                                                            {edit ? (
                                                                <input
                                                                    type="checkbox"
                                                                    className={`toggle ml-2`}
                                                                    style={{
                                                                        borderRadius:
                                                                            "50px",
                                                                        color: value
                                                                            ? "rgb(21 128 61)"
                                                                            : "rgb(185 28 28)",
                                                                    }}
                                                                    onChange={(
                                                                        e,
                                                                    ) => {
                                                                        dispatch(
                                                                            {
                                                                                type: "change_value",
                                                                                payload:
                                                                                    {
                                                                                        inputName:
                                                                                            "booleans." +
                                                                                            key,
                                                                                        inputValue:
                                                                                            e
                                                                                                .target
                                                                                                .checked,
                                                                                    },
                                                                            },
                                                                        );
                                                                    }}
                                                                    checked={
                                                                        formState
                                                                            .booleans[
                                                                            key as keyof typeof formState.booleans
                                                                        ]
                                                                    }
                                                                />
                                                            ) : (
                                                                <div
                                                                    className={`size-3 ${pointer} rounded-full ml-3`}
                                                                    title={
                                                                        generalFields2[
                                                                            idx
                                                                        ]
                                                                    }
                                                                ></div>
                                                            )}
                                                        </div>

                                                        {edit ? (
                                                            <div className="flex flex-col space-y-1">
                                                                <label
                                                                    className={`input input-bordered ${errorBadge ? "input-error" : ""} flex items-center`}
                                                                >
                                                                    <input
                                                                        className="w-full"
                                                                        autoComplete="off"
                                                                        type="text"
                                                                        value={
                                                                            formState
                                                                                .booleansDesc[
                                                                                descKey
                                                                            ]
                                                                        }
                                                                        name={
                                                                            "booleansDesc." +
                                                                            descKey
                                                                        }
                                                                        onChange={(
                                                                            e,
                                                                        ) =>
                                                                            handleChange(
                                                                                e,
                                                                            )
                                                                        }
                                                                    />
                                                                </label>
                                                                {errorBadge && (
                                                                    <span className="badge badge-error self-end">
                                                                        {
                                                                            errorBadge.code
                                                                        }
                                                                    </span>
                                                                )}
                                                            </div>
                                                        ) : (
                                                            <p className="break-words">
                                                                {formState
                                                                    .booleansDesc[
                                                                    descKey
                                                                ] !== "" ? (
                                                                    formState
                                                                        .booleansDesc[
                                                                        descKey
                                                                    ]
                                                                ) : (
                                                                    <span className="text-gray-400">
                                                                        No
                                                                        Description
                                                                    </span>
                                                                )}
                                                            </p>
                                                        )}
                                                    </div>
                                                );
                                            }
                                        },
                                    )}
                                    {Object.entries(formState.rinex).map(
                                        ([key, value], idx) => {
                                            if (
                                                key !== "comments" &&
                                                key !== "navigation_file"
                                            ) {
                                                return (
                                                    <div key={idx}>
                                                        <div className="text-sm font-bold flex items-center">
                                                            {
                                                                generalFields3[
                                                                    idx
                                                                ]
                                                            }
                                                        </div>

                                                        <p className="break-words">
                                                            {value ? (
                                                                formattedDates(
                                                                    new Date(
                                                                        value,
                                                                    ),
                                                                )
                                                            ) : (
                                                                <span className="text-gray-400">
                                                                    No date
                                                                </span>
                                                            )}
                                                        </p>
                                                    </div>
                                                );
                                            } else {
                                                const errorBadge =
                                                    metaMsg?.errors?.errors?.find(
                                                        (error) =>
                                                            error.attr === key,
                                                    );
                                                return (
                                                    <div key={idx}>
                                                        <div className="text-sm font-bold flex items-center justify-between">
                                                            {
                                                                generalFields3[
                                                                    idx
                                                                ]
                                                            }
                                                            {key ===
                                                                "navigation_file" && (
                                                                <button
                                                                    className="btn btn-ghost btn-circle ml-2 -mt-2"
                                                                    onClick={() => {
                                                                        setModals(
                                                                            {
                                                                                show: true,
                                                                                title: "AddFile",
                                                                                type: "add",
                                                                            },
                                                                        );
                                                                        setFileType(
                                                                            "meta",
                                                                        );
                                                                    }}
                                                                    disabled={
                                                                        formState
                                                                            .rinex
                                                                            .navigation_file !==
                                                                        ""
                                                                    }
                                                                >
                                                                    <PlusCircleIcon
                                                                        strokeWidth={
                                                                            1.5
                                                                        }
                                                                        stroke="currentColor"
                                                                        className="size-6"
                                                                    />
                                                                </button>
                                                            )}
                                                        </div>

                                                        {edit ? (
                                                            <div className="flex flex-col space-y-1">
                                                                {key ===
                                                                "comments" ? (
                                                                    <label
                                                                        className={`form-control`}
                                                                        title={
                                                                            errorBadge
                                                                                ? errorBadge.detail
                                                                                : ""
                                                                        }
                                                                    >
                                                                        <textarea
                                                                            className={`textarea textarea-bordered w-full ${errorBadge ? "textarea-error" : ""}`}
                                                                            autoComplete="off"
                                                                            value={
                                                                                formState
                                                                                    .rinex[
                                                                                    key as keyof typeof formState.rinex
                                                                                ] ??
                                                                                ""
                                                                            }
                                                                            name={
                                                                                "rinex." +
                                                                                key
                                                                            }
                                                                            onChange={(
                                                                                e,
                                                                            ) =>
                                                                                handleChange(
                                                                                    e,
                                                                                )
                                                                            }
                                                                        />
                                                                        {errorBadge && (
                                                                            <span className="badge badge-error self-end">
                                                                                {
                                                                                    errorBadge.code
                                                                                }
                                                                            </span>
                                                                        )}
                                                                    </label>
                                                                ) : (
                                                                    <div className="bg-neutral-content p-4 rounded-md flex-grow flex items-center">
                                                                        {formState
                                                                            .rinex[
                                                                            key as keyof typeof formState.rinex
                                                                        ] && (
                                                                            <button
                                                                                className="btn btn-ghost btn-circle mr-4"
                                                                                onClick={() => {
                                                                                    setModals(
                                                                                        {
                                                                                            show: true,
                                                                                            title: "ConfirmDelete",
                                                                                            type: "edit",
                                                                                        },
                                                                                    );
                                                                                    setFileType(
                                                                                        "meta",
                                                                                    );
                                                                                }}
                                                                            >
                                                                                <TrashIcon className="size-6 text-red-600" />
                                                                            </button>
                                                                        )}
                                                                        <p className="break-words">
                                                                            {formState
                                                                                .rinex[
                                                                                key as keyof typeof formState.rinex
                                                                            ] ? (
                                                                                formState
                                                                                    .rinex[
                                                                                    key as keyof typeof formState.rinex
                                                                                ]
                                                                            ) : (
                                                                                <span className="text-gray-400">
                                                                                    No
                                                                                    info
                                                                                </span>
                                                                            )}
                                                                        </p>
                                                                        {formState
                                                                            .rinex[
                                                                            key as keyof typeof formState.rinex
                                                                        ] && (
                                                                            <a
                                                                                className="btn-circle btn-ghost flex justify-center w-4/12"
                                                                                download={
                                                                                    formState
                                                                                        .rinex
                                                                                        .navigation_file
                                                                                }
                                                                                href={`data:application/pdf;base64,${stationMeta?.navigation_actual_file}`}
                                                                            >
                                                                                <ArrowDownTrayIcon className="size-6 self-center" />
                                                                            </a>
                                                                        )}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        ) : (
                                                            <p className="break-words">
                                                                {formState
                                                                    .rinex[
                                                                    key as keyof typeof formState.rinex
                                                                ] &&
                                                                formState.rinex[
                                                                    key as keyof typeof formState.rinex
                                                                ] !== "" ? (
                                                                    formState
                                                                        .rinex[
                                                                        key as keyof typeof formState.rinex
                                                                    ]
                                                                ) : (
                                                                    <span className="text-gray-400">
                                                                        No info
                                                                    </span>
                                                                )}
                                                            </p>
                                                        )}
                                                    </div>
                                                );
                                            }
                                        },
                                    )}
                                </div>
                            </div>
                        </div>

                        <div className="flex flex-col items-center">
                            <h3 className="font-bold text-xl my-2">
                                Monument Photo
                            </h3>
                            <img
                                className="size-60 object-contain"
                                src={
                                    monumentType.find(
                                        (mt) =>
                                            mt.id ===
                                            Number(stationMeta?.monument_type),
                                    )?.photo_file
                                        ? "data:image/png;base64," +
                                          monumentType.find(
                                              (mt) =>
                                                  mt.id ===
                                                  Number(
                                                      stationMeta?.monument_type,
                                                  ),
                                          )?.photo_file
                                        : defPhoto
                                }
                                alt={
                                    monumentType.find(
                                        (mt) =>
                                            mt.id ===
                                            Number(stationMeta?.monument_type),
                                    )?.name
                                }
                            />
                        </div>

                        <div className="card bg-base-200 grow shadow-xl mr-4">
                            <h2 className="card-title border-b-2 border-base-300 p-2 justify-between">
                                Geodetic Coordinates
                                <button className="btn btn-ghost btn-circle">
                                    <ClipboardDocumentIcon
                                        className="size-6"
                                        title={"copy coordinates"}
                                        onClick={() => {
                                            navigator.clipboard.writeText(
                                                "LATITUDE: " +
                                                    formState.station.lat +
                                                    ",LONGITUDE: " +
                                                    formState.station.lon +
                                                    ",HEIGHT: " +
                                                    formState.station.height,
                                            );
                                        }}
                                    />
                                </button>
                            </h2>
                            <div className="card-body">
                                <div className="grid grid-cols-3 gap-2">
                                    {["lat", "lon", "height"].map(
                                        (key, idx) => {
                                            if (key) {
                                                const latLon = ["lat", "lon"];

                                                const errorBadge =
                                                    stationMsg?.errors?.errors?.find(
                                                        (error) =>
                                                            error.attr === key,
                                                    );

                                                return (
                                                    <div key={idx}>
                                                        <div className="text-sm font-bold flex items-center">
                                                            {key === "lat"
                                                                ? "Latitude"
                                                                : key === "lon"
                                                                  ? "Longitude"
                                                                  : "Height"}
                                                        </div>
                                                        {edit ? (
                                                            <div className="flex flex-col space-y-1">
                                                                <label
                                                                    className={`input input-bordered ${errorBadge ? "input-error" : ""} flex items-center`}
                                                                    title={
                                                                        errorBadge
                                                                            ? errorBadge.detail
                                                                            : ""
                                                                    }
                                                                >
                                                                    <input
                                                                        className="w-full"
                                                                        autoComplete="off"
                                                                        type="text"
                                                                        value={
                                                                            formState
                                                                                .station[
                                                                                key as keyof typeof formState.station
                                                                            ] ??
                                                                            ""
                                                                        }
                                                                        title={
                                                                            errorBadge
                                                                                ? errorBadge.detail
                                                                                : ""
                                                                        }
                                                                        name={
                                                                            "station." +
                                                                            key
                                                                        }
                                                                        onChange={(
                                                                            e,
                                                                        ) =>
                                                                            handleChange(
                                                                                e,
                                                                            )
                                                                        }
                                                                    />
                                                                </label>
                                                                {errorBadge && (
                                                                    <span className="badge badge-error self-end">
                                                                        {
                                                                            errorBadge.code
                                                                        }
                                                                    </span>
                                                                )}
                                                            </div>
                                                        ) : (
                                                            <p className="break-all">
                                                                {formState
                                                                    .station[
                                                                    key as keyof typeof formState.station
                                                                ] ? (
                                                                    latLon.includes(
                                                                        key,
                                                                    ) ? (
                                                                        decimalToDMS(
                                                                            Number(
                                                                                formState
                                                                                    .station[
                                                                                    key as keyof typeof formState.station
                                                                                ],
                                                                            ),
                                                                            key ===
                                                                                "lat",
                                                                        )
                                                                    ) : (
                                                                        Number(
                                                                            formState
                                                                                .station[
                                                                                key as keyof typeof formState.station
                                                                            ],
                                                                        ) + " m"
                                                                    )
                                                                ) : (
                                                                    <span className="text-gray-400">
                                                                        No {key}
                                                                    </span>
                                                                )}
                                                            </p>
                                                        )}
                                                    </div>
                                                );
                                            }
                                        },
                                    )}
                                </div>
                            </div>
                        </div>
                        <div className="card bg-base-200 grow shadow-xl">
                            <h2 className="card-title border-b-2 border-base-300 p-2 justify-between">
                                Cartesian Coordinates
                                <button className="btn btn-ghost btn-circle">
                                    <ClipboardDocumentIcon
                                        className="size-6"
                                        title={"copy coordinates"}
                                        onClick={() => {
                                            navigator.clipboard.writeText(
                                                "X: " +
                                                    formState.station.auto_x +
                                                    ",Y: " +
                                                    formState.station.auto_y +
                                                    ",Z: " +
                                                    formState.station.auto_z,
                                            );
                                        }}
                                    />
                                </button>
                            </h2>
                            <div className="card-body">
                                <div className="grid grid-cols-3 md:grid-cols-2 grid-flow-dense gap-2">
                                    {["auto_x", "auto_y", "auto_z"].map(
                                        (key, idx) => {
                                            if (key) {
                                                const errorBadge =
                                                    stationMsg?.errors?.errors?.find(
                                                        (error) =>
                                                            error.attr === key,
                                                    );

                                                return (
                                                    <div key={idx}>
                                                        <div className="text-sm font-bold flex items-center">
                                                            {key === "auto_x"
                                                                ? "X"
                                                                : key ===
                                                                    "auto_y"
                                                                  ? "Y"
                                                                  : "Z"}
                                                        </div>
                                                        {edit ? (
                                                            <div className="flex flex-col space-y-1">
                                                                <label
                                                                    className={`input input-bordered ${errorBadge ? "input-error" : ""} flex items-center`}
                                                                >
                                                                    <input
                                                                        className="w-full"
                                                                        autoComplete="off"
                                                                        type="text"
                                                                        value={
                                                                            formState
                                                                                .station[
                                                                                key as keyof typeof formState.station
                                                                            ] ??
                                                                            ""
                                                                        }
                                                                        title={
                                                                            errorBadge
                                                                                ? errorBadge.detail
                                                                                : ""
                                                                        }
                                                                        name={
                                                                            "station." +
                                                                            key
                                                                        }
                                                                        onChange={(
                                                                            e,
                                                                        ) =>
                                                                            handleChange(
                                                                                e,
                                                                            )
                                                                        }
                                                                    />
                                                                </label>
                                                                {errorBadge && (
                                                                    <span className="badge badge-error self-end">
                                                                        {
                                                                            errorBadge.code
                                                                        }
                                                                    </span>
                                                                )}
                                                            </div>
                                                        ) : (
                                                            <p className="break-words">
                                                                {formState
                                                                    .station[
                                                                    key as keyof typeof formState.station
                                                                ] ? (
                                                                    Number(
                                                                        formState
                                                                            .station[
                                                                            key as keyof typeof formState.station
                                                                        ],
                                                                    ) + " m"
                                                                ) : (
                                                                    <span className="text-gray-400">
                                                                        No {key}
                                                                    </span>
                                                                )}
                                                            </p>
                                                        )}
                                                    </div>
                                                );
                                            }
                                        },
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="grid grid-cols-1 space-y-4 grid-flow-dense">
                        <div className="card bg-base-200 grow shadow-xl">
                            <h2 className="card-title border-b-2 border-base-300 p-2 justify-between">
                                Equipment
                            </h2>
                            <div className="card-body">
                                <div className="grid grid-cols-4 md:grid-cols-2 grid-flow-dense gap-2">
                                    {Object.entries(formState.equipment).map(
                                        ([key, value], idx) => {
                                            if (key) {
                                                return (
                                                    <div key={idx}>
                                                        <div className="text-sm font-bold flex items-center">
                                                            {
                                                                equipmentFields[
                                                                    idx
                                                                ]
                                                            }
                                                        </div>

                                                        <p className="break-words">
                                                            {value ? (
                                                                value
                                                            ) : (
                                                                <span className="text-gray-400">
                                                                    No {key}
                                                                </span>
                                                            )}
                                                        </p>
                                                    </div>
                                                );
                                            }
                                        },
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="grid grid-cols-1 space-y-4 grid-flow-dense">
                        <div className="card bg-base-200 grow shadow-xl">
                            <h2 className="card-title border-b-2 border-base-300 p-2 justify-between">
                                Attached Files
                                <button
                                    className="btn btn-ghost btn-circle ml-2"
                                    onClick={() => {
                                        setModals({
                                            show: true,
                                            title: "AddFile",
                                            type: "add",
                                        });
                                    }}
                                >
                                    <PlusCircleIcon
                                        strokeWidth={1.5}
                                        stroke="currentColor"
                                        className="w-8 h-10"
                                    />
                                </button>
                            </h2>
                            <div className="card-body">
                                <div
                                    className={`grid ${files && files.length > 0 ? "grid-cols-3 md:grid-cols-2" : "grid-cols-1"} grid-flow-dense gap-2`}
                                >
                                    {files && files.length > 0 ? (
                                        files.map((file) => {
                                            return (
                                                <div
                                                    className="flex items-center w-full rounded-md bg-neutral-content"
                                                    key={
                                                        file.filename + file.id
                                                    }
                                                >
                                                    <div className="flex-grow overflow-hidden ">
                                                        <div className="p-6 flex w-full justify-between items-center">
                                                            <button
                                                                className="btn btn-ghost btn-circle mr-4"
                                                                onClick={() => {
                                                                    setModals({
                                                                        show: true,
                                                                        title: "ConfirmDelete",
                                                                        type: "edit",
                                                                    });
                                                                    setFileToDel(
                                                                        file.id,
                                                                    );
                                                                }}
                                                            >
                                                                <TrashIcon className="size-8 text-red-600" />
                                                            </button>
                                                            <div className="flex flex-col w-8/12 text-pretty break-words max-w-full">
                                                                <h2 className="card-title">
                                                                    {
                                                                        file.filename
                                                                    }
                                                                </h2>
                                                                <p>
                                                                    {
                                                                        file.description
                                                                    }
                                                                </p>
                                                            </div>
                                                            <a
                                                                className="btn-circle btn-ghost flex justify-center w-4/12"
                                                                download={
                                                                    file.filename
                                                                }
                                                                href={`data:application/pdf;base64,${file.actual_file}`}
                                                            >
                                                                <ArrowDownTrayIcon className="size-6 self-center" />
                                                            </a>
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })
                                    ) : (
                                        <div className="text-center text-neutral text-2xl font-bold w-full rounded-md bg-neutral-content p-6">
                                            There is no files registered
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
            {edit && (
                <div className="w-full flex flex-col items-center justify-center">
                    <Alert
                        msg={
                            metaMsg?.status === 200 &&
                            stationMsg?.status === 200
                                ? metaMsg
                                : metaMsg?.status !== 200
                                  ? metaMsg
                                  : stationMsg?.status !== 200
                                    ? stationMsg
                                    : undefined
                        }
                    />
                    <button
                        className="btn btn-success w-[140px] mt-4"
                        onClick={() => updateMetadata()}
                        disabled={loading || updateLoading}
                    >
                        {updateLoading && (
                            <div
                                className="inline-block size-6
                                mx-2 animate-spin rounded-full border-4 border-solid border-current border-e-transparent align-[-0.125em] text-white motion-reduce:animate-[spin_1.5s_linear_infinite]"
                                role="status"
                            ></div>
                        )}
                        UPDATE
                    </button>
                </div>
            )}

            {modals && modals?.title === "AddFile" && (
                <StationAddFileModal
                    stationId={stationId}
                    stationMetaId={stationMeta?.station}
                    meta={fileType === "meta"}
                    refetchStationMeta={() => {
                        refetchStationMeta && refetchStationMeta();
                        setFileType("none");
                    }}
                    reFetch={() => {
                        getFiles();
                        setFileType("none");
                    }}
                    setStateModal={setModals}
                />
            )}

            {modals && modals?.title === "ConfirmDelete" && (
                <ConfirmDeleteModal
                    msg={fileMsg}
                    loading={loading}
                    confirmRemove={() =>
                        fileType === "meta"
                            ? delFileMeta()
                            : delFile(fileToDel as number)
                    }
                    closeModal={() => {
                        setModals({
                            show: false,
                            title: "",
                            type: "edit",
                        });
                        setFileType("none");

                        setFileMsg(undefined);
                    }}
                />
            )}
        </Modal>
    );
};

export default StationMetadataModal;
