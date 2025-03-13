import { useState } from "react";
import { Spinner } from "@componentsReact";

import {
    ArrowDownIcon,
    ArrowLongUpIcon,
    CheckCircleIcon,
    ExclamationCircleIcon,
    ExclamationTriangleIcon,
    PlusIcon,
    QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";

import { formattedDates, formatValue, woTz } from "@utils";

import {
    RinexData,
    RinexItem,
    RinexObject,
    RinexRelatedStationInfo,
} from "@types";

interface TableProps {
    loading?: boolean;
    titles: string[];
    sameGroup: boolean;
    fullData: RinexObject[];
    data: RinexObject[];
    setModals: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
    setRinexStationInfoRelated: React.Dispatch<
        React.SetStateAction<RinexRelatedStationInfo[] | undefined>
    >;
    setRinexGroup: React.Dispatch<
        React.SetStateAction<RinexItem[] | undefined>
    >;
    setSingleRinex: React.Dispatch<React.SetStateAction<RinexData | undefined>>;
    setExtendTypeRinex: React.Dispatch<
        React.SetStateAction<"up" | "down" | undefined>
    >;
}

const RinexTable = ({
    loading,
    titles,
    sameGroup,
    fullData,
    data,
    setModals,
    setRinexStationInfoRelated,
    setRinexGroup,
    setSingleRinex,
    setExtendTypeRinex,
}: TableProps) => {
    const [tooltipId, setTooltipId] = useState<string | undefined>(undefined);

    //  Background: red ⇾ no station info; light red ⇾ no station info but completion < 0.5; gray ⇾ station info but completion < 0.5; green ⇾ all good

    // BACKGROUND: RED -> SI NO TIENE STATION INFO Y COMPLETION >= 0.5 ;
    //  LIGHT RED -> NO STATION INFO Y COMPLETION < 0.5;                      // SOLO NECESITO VER EL has_station_info y el Completion de la data.
    //  GRAY -> STATION INFO Y COMPLETION < 0.5;
    //  GREEN -> ALL GOOD // TIENE STATION INFO Y TIENE COMPLETION >= 0.5

    // STATUSES
    // 1 - has_station_info: boolean
    // 2 - has_multiple_station_info_gap: boolean
    // 3 - metadata_mismatch: boolean
    // 4 - gap_type: ["BEFORE FIRST STATIONINFO", "BETWEEN TWO STATIONINFO", "AFTER LAST STATIONINFO", "NO STATION INFO"]

    //  ALERT   = station information ok but mismatch between RINEX metadata and station information (see red-underlined fields)
    //  RED SIGN  = missing station information record
    //  GREEN SIGN = station information ok

    // SI NO TIENE STATION INFO -> RED SIGN -> SOLO ME FIJO has_station_info.

    // SI TIENE STATION INFO Y metadata_mismatch FALSE,
    // ES INDIFERENTE has_multiple_station_info_gap XQ ESTA DENTRO DEL STATION INFO -> GREEN SIGN
    //  -> SOLO ME FIJO has_station_info Y metadata_mismatch

    // SI TIENE STATION INFO Y metadata_mismatch TRUE -> ALERT -> SOLO ME FIJO has_station_info Y metadata_mismatch.

    // SI has_multiple_station_info_gap TRUE -> ICONO NO DEFINIDO (TODAVIA) -> SOLO ME FIJO has_multiple_station_info_gap.
    // CASO ESPECIAL CUANDO EL RINEX ESTA DENTRO DE DOS STATION INFO A LA VEZ.

    // ------------------------- INFO
    // PRIMER NIVEL/COLUMNA DE INFO
    // SI NO TENGO STATION INFO -> "+" -> SOLO ME FIJO has_station_info

    // SI TENGO STATION INFO -> "V" -> SOLO ME FIJO has_station_info
    // SI EL PRIMER RINEX TIENE "FLECHA ARRIBA" -> "FLECHA ARRIBA" -> SOLO ME FIJO gap_type DEL RINEX SEA "between..." o "before..."
    // -> SI EL RINEX NO TIENE "FLECHA ARRIBA" -> NULL

    // SI EL ULTIMO RINEX TIENE "FLECHA ABAJO" -> "FLECHA ABAJO" -> SOLO ME FIJO gap_type DEL RINEX SEA "between..." o "after..."
    // -> SI EL RINEX NO TIENE "FLECHA ABAJO" -> NULL

    // SEGUNDO NIVEL/COLUMNA DE INFO
    // SI NO TENGO STATION INFO -> "+" -> SOLO ME FIJO has_station_info
    // SI gap_type == "BEFORE FIRST STATIONINFO" -> FLECHA ARRIBA, DISABLE FLECHA ABAJO -> SOLO ME FIJO gap_type
    // SI gap_type == "BETWEEN TWO STATIONINFO" -> FLECHA ARRIBA Y ABAJO -> SOLO ME FIJO gap_type
    // SI gap_type == "AFTER LAST STATIONINFO" -> FLECHA ABAJO, DISABLE FLECHA ARRIBA-> SOLO ME FIJO gap_type
    // SI gap_type == "NO STATION INFO" -> NO HAGO NADA O DISABLE DE FLECHAS -> SOLO ME FIJO gap_type
    // ANIDADO AL "+"

    // SI TENGO STATION INFO -> "E" -> SOLO ME FIJO has_station_info

    // ------------------------- INFO

    // ANNOTATIONS

    // FLECHA ARRIBA DE PRIMER NIVEL -> ACTUALIZAR EL PRIMER STATION INFO DEL ARRAY, PONIENDO LA DATE START (DEL STATION INFO) DEL PRIMER RINEX ASOCIADO (DATE START DEL RINEX).
    // FLECHA ABAJO DE PRIMER NIVEL -> ACTUALIZAR EL ULTIMO STATION INFO DEL ARRAY, PONIENDO LA DATE END (DEL STATION INFO) DEL ULTIMO RINEX ASOCIADO (DATE END DEL RINEX).

    // FLECHAS SEGUNDO NIVEL -> BACK.

    // FLECHAS SEGUNDO NIVEL -> MANDO EL API_ID DEL RINEX AL ENDPOINT DEL BACK.

    // LA "E" ABRE EL MODAL DE TODOS LOS STATION INFO RELACIONADOS CON EL SUBGRUPO DEL RINEX.

    // EL "+"  MODAL CON LA DISPOSICION DE DOS OPCIONES.
    // 1er OPCION) DEBE ABRIR EL MODAL DE TODOS LOS STATION INFO CON EL MODAL DEL ADD Y LOS DATOS DE RINEX RELLENADOS EN EL STATION INFO MODAL.
    // 2da OPCION) CREAR EL STATION INFO DESDE UNA IMPORTACION
    // ------------

    const rinexInfoFirstLevel = (fnData: RinexObject) => {
        // PREDOMINA SI RINEX.HAST_STATION_INFO ES TRUE, POR SOBRE EL FALSE.
        // DEBERÍA ANALIZAR EL ARRAY DE LOS RINEX Y RETORNAR LA CONCATENACIÓN DE RESULTADOS (SI TIENE FLECHA ARRIBA, ETC).
        // SI MAS DE UNO TIENE EL MISMO GAP_TYPE, NO DEBERÍA REPETIRSE.
        // RINEX AHORA ES UN OBJETO DE RINEXS

        const rinexArr = fnData.rinex;

        let symbol: JSX.Element | null = null;

        rinexArr.forEach((rinexItem) => {
            const hasStationInfo = rinexItem.rinex.some(
                (r) => r.has_station_info,
            );

            if (hasStationInfo) {
                symbol = (
                    <button
                        type="button"
                        className="hover:scale-125 transition-all"
                        onClick={() => {
                            setRinexStationInfoRelated(
                                fnData.related_station_info,
                            );

                            setModals({
                                show: true,
                                title: "Information",
                                type: "none",
                            });
                        }}
                    >
                        V
                    </button>
                );
            } else if (!symbol) {
                symbol = (
                    <button
                        className="hover:scale-125 transition-all"
                        onMouseEnter={() => setTooltipId(fnData.groupId)}
                        onMouseLeave={() => setTooltipId(undefined)}
                    >
                        <PlusIcon className="size-4 text-black" />
                    </button>
                );
            }
        });

        return (
            <div
                className="flex flex-col items-center justify-center space-y-2"
                id={`firstLevelSymbol-${fnData.groupId}`}
            >
                {symbol}
            </div>
        );
    };

    const rinexInfoSecondLevel = (data: RinexItem) => {
        let firstRinexArrowUp: JSX.Element | null = null;
        let firstRinexArrowDown: JSX.Element | null = null;

        let symbol: JSX.Element | null = null;

        const rinex = data.rinex[0];

        if (
            rinex?.gap_type === "BEFORE FIRST STATIONINFO" ||
            rinex?.gap_type === "BETWEEN TWO STATIONINFO"
        ) {
            firstRinexArrowUp = (
                <button
                    className="hover:scale-125 transition-all"
                    onClick={() => {
                        setSingleRinex(rinex);
                        setExtendTypeRinex("up");
                        setModals({
                            show: true,
                            title: "RinexExtend",
                            type: "none",
                        });
                    }}
                >
                    <ArrowLongUpIcon className="size-4 " />
                </button>
            );
        }

        if (
            rinex?.gap_type === "AFTER LAST STATIONINFO" ||
            rinex?.gap_type === "BETWEEN TWO STATIONINFO"
        ) {
            firstRinexArrowDown = (
                <button
                    className="hover:scale-125 transition-all"
                    onClick={() => {
                        setSingleRinex(rinex);
                        setExtendTypeRinex("down");
                        setModals({
                            show: true,
                            title: "RinexExtend",
                            type: "none",
                        });
                    }}
                >
                    <ArrowDownIcon className="size-4 " />
                </button>
            );
        }

        const hasStationInfo = rinex.has_station_info;

        if (hasStationInfo) {
            symbol = (
                <button
                    type="button"
                    className="hover:scale-125 transition-all"
                    onClick={() => {
                        setRinexStationInfoRelated(data.related_station_info);
                        setModals({
                            show: true,
                            title: "Information",
                            type: "none",
                        });
                    }}
                >
                    E
                </button>
            );
        } else if (!symbol && !rinex.has_multiple_station_info_gap) {
            symbol = (
                <button
                    className="hover:scale-125 transition-all"
                    onMouseEnter={() => setTooltipId(String(rinex.api_id))}
                    onMouseLeave={() => setTooltipId(undefined)}
                >
                    <PlusIcon className="size-4" />
                </button>
            );
        }

        return (
            <div className="flex items-center justify-center space-x-2 ">
                {symbol}
                {firstRinexArrowUp}
                {firstRinexArrowDown}
            </div>
        );
    };

    const rinexStatus = (rinex: any) => {
        if (rinex.has_multiple_station_info_gap) {
            return <QuestionMarkCircleIcon className="size-7 fill-gray-300" />;
        }
        if (!rinex.has_station_info) {
            return <ExclamationCircleIcon className="size-7 fill-red-600" />;
        } else if (rinex.metadata_mismatch.length > 0) {
            return (
                <ExclamationTriangleIcon className="size-7 fill-yellow-400" />
            );
        } else {
            return <CheckCircleIcon className="size-7 fill-green-500 " />;
        }
    };

    const rinexBackground = (rinex: any) => {
        if (!rinex.has_station_info || rinex.has_multiple_station_info_gap) {
            if (rinex.completion && rinex.completion < 0.5) {
                return "bg-red-300";
            } else {
                return "bg-red-400";
            }
        } else {
            if (rinex.completion && rinex.completion < 0.5) {
                return "bg-gray-300";
            } else {
                return "bg-green-300";
            }
        }
    };

    return (
        <div className={tooltipId ? "overflow-x-clip" : "overflow-x-auto pb-2"}>
            <table className="table ">
                <thead>
                    <tr className="">
                        {titles.length > 0 ? (
                            <>
                                <th
                                    className="text-center text-neutral border-[1px] border-base-content"
                                    colSpan={2}
                                >
                                    INFO
                                </th>
                                <th className="text-center text-neutral border-[1px] border-base-content">
                                    STATUS
                                </th>
                            </>
                        ) : (
                            titles.length === 0 &&
                            !loading && (
                                <th
                                    className="text-center text-neutral text-2xl"
                                    colSpan={titles.length + 2}
                                >
                                    There is no Rinex data to show
                                </th>
                            )
                        )}

                        {titles.map((title, index) => (
                            <th
                                className="text-center text-neutral max-w-[200px] border-[1px] border-base-content"
                                key={index}
                            >
                                {title
                                    ? title?.toUpperCase().replace(/_/g, " ")
                                    : ""}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody className="">
                    {loading ? (
                        <tr>
                            <td
                                colSpan={titles.length + 2}
                                className="relative h-[200px]"
                            >
                                <div className="absolute inset-0 flex justify-center items-center">
                                    <Spinner size="lg" />
                                </div>
                            </td>
                        </tr>
                    ) : (
                        data.map((first, stationIndex) => {
                            const fullGroup = fullData.find(
                                (item) => item.groupId === first.groupId,
                            );

                            const rowSpan = first.rinex.reduce(
                                (acc, rinexItem) =>
                                    acc + rinexItem.rinex.length,
                                0,
                            );

                            return first.rinex.map((rinexItem, rinexIndex) => {
                                const rinexItemLength = rinexItem.rinex.length;

                                return rinexItem.rinex.map(
                                    (rinex, rinexSubIndex) => {
                                        const {
                                            api_id, //eslint-disable-line
                                            filtered, //eslint-disable-line
                                            ...rinexWithoutApiId
                                        } = rinex;

                                        const isSameGroup =
                                            stationIndex === 0 &&
                                            rinexIndex === 0 &&
                                            sameGroup;

                                        return (
                                            <tr
                                                className="h-full"
                                                key={`${stationIndex}-${rinexIndex}-${rinexSubIndex}`}
                                            >
                                                {rinexIndex === 0 &&
                                                    rinexSubIndex === 0 && (
                                                        <>
                                                            <th
                                                                rowSpan={
                                                                    rowSpan
                                                                }
                                                                className="relative border-[1px] border-base-content h-full"
                                                                scope="rowgroup"
                                                            >
                                                                {isSameGroup &&
                                                                    first.groupId !==
                                                                        "group-0" && (
                                                                        <div className="absolute top-0">
                                                                            ...
                                                                        </div>
                                                                    )}
                                                                <div className="relative ">
                                                                    {rinexInfoFirstLevel(
                                                                        first,
                                                                    )}

                                                                    {tooltipId ===
                                                                        first.groupId && (
                                                                        <div
                                                                            className="absolute -top-[78px] bg-gray-800 text-white p-2 rounded 
                                            text-pretty whitespace-nowrap w-[240px] z-50 overflow-visible"
                                                                            onMouseEnter={() =>
                                                                                setTooltipId(
                                                                                    first.groupId,
                                                                                )
                                                                            }
                                                                            onMouseLeave={() =>
                                                                                setTooltipId(
                                                                                    undefined,
                                                                                )
                                                                            }
                                                                        >
                                                                            <div className="flex space-x-4 items-center">
                                                                                <button
                                                                                    onClick={() => {
                                                                                        setRinexGroup(
                                                                                            undefined,
                                                                                        );
                                                                                        setModals(
                                                                                            {
                                                                                                show: true,
                                                                                                title: "RinexAdd",
                                                                                                type: "add",
                                                                                            },
                                                                                        );
                                                                                    }}
                                                                                    className="w-[45%] hover:bg-gray-400 bg-gray-500 rounded p-4"
                                                                                >
                                                                                    By
                                                                                    file
                                                                                </button>
                                                                                <span>
                                                                                    Or
                                                                                </span>
                                                                                <button
                                                                                    onClick={() => {
                                                                                        setRinexGroup(
                                                                                            fullGroup?.rinex,
                                                                                        );

                                                                                        setModals(
                                                                                            {
                                                                                                show: true,
                                                                                                title: "EditStats",
                                                                                                type: "none",
                                                                                            },
                                                                                        );
                                                                                    }}
                                                                                    className="w-[45%] hover:bg-gray-400 bg-gray-500 rounded p-4"
                                                                                >
                                                                                    By
                                                                                    rinex
                                                                                </button>
                                                                            </div>
                                                                            <div
                                                                                className="absolute top-[100%] left-3 w-0 
                                                -translate-x-2/4 h-0 border-l-8 border-l-transparent 
                                                border-r-8 border-r-transparent border-t-8
                                                border-t-gray-800"
                                                                            ></div>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            </th>
                                                            <th
                                                                rowSpan={
                                                                    rinexItemLength
                                                                }
                                                                className="relative h-full border-[1px] border-base-content"
                                                                // style={{
                                                                //     borderRight:
                                                                //         "1px solid #e2e8f0",
                                                                // }}
                                                                scope="rowgroup"
                                                            >
                                                                <div className="relative">
                                                                    {tooltipId ===
                                                                        String(
                                                                            rinex.api_id,
                                                                        ) && (
                                                                        <div
                                                                            className="absolute -top-[75px] bg-gray-800 text-white p-2 rounded 
                                            text-pretty whitespace-nowrap w-[240px] z-50 overflow-visible"
                                                                            onMouseEnter={() =>
                                                                                setTooltipId(
                                                                                    String(
                                                                                        rinex.api_id,
                                                                                    ),
                                                                                )
                                                                            }
                                                                            onMouseLeave={() =>
                                                                                setTooltipId(
                                                                                    undefined,
                                                                                )
                                                                            }
                                                                        >
                                                                            <div className="flex space-x-4 items-center">
                                                                                <button
                                                                                    onClick={() => {
                                                                                        setSingleRinex(
                                                                                            undefined,
                                                                                        );
                                                                                        setModals(
                                                                                            {
                                                                                                show: true,
                                                                                                title: "RinexAdd",
                                                                                                type: "add",
                                                                                            },
                                                                                        );
                                                                                    }}
                                                                                    className="w-[45%] hover:bg-gray-400 bg-gray-500 rounded p-4"
                                                                                >
                                                                                    By
                                                                                    file
                                                                                </button>
                                                                                <span>
                                                                                    Or
                                                                                </span>
                                                                                <button
                                                                                    onClick={() => {
                                                                                        setSingleRinex(
                                                                                            rinex,
                                                                                        );

                                                                                        setModals(
                                                                                            {
                                                                                                show: true,
                                                                                                title: "EditStats",
                                                                                                type: "none",
                                                                                            },
                                                                                        );
                                                                                    }}
                                                                                    className="w-[45%] hover:bg-gray-400 bg-gray-500 rounded p-4"
                                                                                >
                                                                                    By
                                                                                    rinex
                                                                                </button>
                                                                            </div>
                                                                            <div
                                                                                className="absolute top-[100%] left-3 w-0 
                                                -translate-x-2/4 h-0 border-l-8 border-l-transparent 
                                                border-r-8 border-r-transparent border-t-8
                                                border-t-gray-800"
                                                                            ></div>
                                                                        </div>
                                                                    )}

                                                                    {rinexInfoSecondLevel(
                                                                        rinexItem,
                                                                    )}
                                                                </div>
                                                            </th>
                                                        </>
                                                    )}
                                                {rinexIndex > 0 &&
                                                    rinexSubIndex === 0 && (
                                                        <th
                                                            rowSpan={
                                                                rinexItemLength
                                                            }
                                                            scope="rowgroup"
                                                            className="relative h-full border-[1px] border-base-content "
                                                        >
                                                            <div className="relative ">
                                                                {tooltipId ===
                                                                    String(
                                                                        rinex.api_id,
                                                                    ) && (
                                                                    <div
                                                                        className="absolute -top-[75px] bg-gray-800 text-white p-2 rounded 
                                            text-pretty whitespace-nowrap w-[240px] z-50 overflow-visible"
                                                                        onMouseEnter={() =>
                                                                            setTooltipId(
                                                                                String(
                                                                                    rinex.api_id,
                                                                                ),
                                                                            )
                                                                        }
                                                                        onMouseLeave={() =>
                                                                            setTooltipId(
                                                                                undefined,
                                                                            )
                                                                        }
                                                                    >
                                                                        <div className="flex space-x-4 items-center">
                                                                            <button
                                                                                onClick={() => {
                                                                                    setSingleRinex(
                                                                                        undefined,
                                                                                    );
                                                                                    setModals(
                                                                                        {
                                                                                            show: true,
                                                                                            title: "RinexAdd",
                                                                                            type: "add",
                                                                                        },
                                                                                    );
                                                                                }}
                                                                                className="w-[45%] hover:bg-gray-400 bg-gray-500 rounded p-4"
                                                                            >
                                                                                By
                                                                                file
                                                                            </button>
                                                                            <span>
                                                                                Or
                                                                            </span>
                                                                            <button
                                                                                onClick={() => {
                                                                                    setSingleRinex(
                                                                                        rinex,
                                                                                    );

                                                                                    setModals(
                                                                                        {
                                                                                            show: true,
                                                                                            title: "EditStats",
                                                                                            type: "none",
                                                                                        },
                                                                                    );
                                                                                }}
                                                                                className="w-[45%] hover:bg-gray-400 bg-gray-500 rounded p-4"
                                                                            >
                                                                                By
                                                                                rinex
                                                                            </button>
                                                                        </div>
                                                                        <div
                                                                            className="absolute top-[100%] left-3 w-0 
                                                -translate-x-2/4 h-0 border-l-8 border-l-transparent 
                                                border-r-8 border-r-transparent border-t-8
                                                border-t-gray-800"
                                                                        ></div>
                                                                    </div>
                                                                )}

                                                                {rinexInfoSecondLevel(
                                                                    rinexItem,
                                                                )}
                                                            </div>
                                                        </th>
                                                    )}

                                                <td
                                                    className="relative w-full border-[1px] border-base-content"
                                                    style={{ padding: 0 }}
                                                >
                                                    <div className="flex flex-col items-center justify-center">
                                                        {rinexStatus(
                                                            rinexWithoutApiId,
                                                        )}
                                                    </div>
                                                </td>
                                                {Object.entries(
                                                    rinexWithoutApiId,
                                                ).map(([key, value], index) => {
                                                    (key as string).includes(
                                                        "f_year",
                                                    ) &&
                                                        (value =
                                                            Number(
                                                                value,
                                                            ).toFixed(3));

                                                    const keysNotToDisplay = [
                                                        "related_station_info",
                                                        "has_station_info",
                                                        "has_multiple_station_info_gap",
                                                        "metadata_mismatch",
                                                        "gap_type",
                                                        "network_code",
                                                        "station_code",
                                                    ];

                                                    const valuesToUnderline =
                                                        rinexWithoutApiId[
                                                            "metadata_mismatch"
                                                        ];

                                                    if (
                                                        keysNotToDisplay.includes(
                                                            key,
                                                        )
                                                    ) {
                                                        return null;
                                                    }

                                                    const isDateFunc = (
                                                        val: any,
                                                    ) => {
                                                        const isoDateRegex =
                                                            /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$/;
                                                        return (
                                                            typeof val ===
                                                                "string" &&
                                                            isoDateRegex.test(
                                                                val,
                                                            )
                                                        );
                                                    };

                                                    const isDate =
                                                        isDateFunc(value) &&
                                                        value !== "";

                                                    return (
                                                        <td
                                                            className={`${rinexBackground(
                                                                rinex,
                                                            )} text-center max-w-[200px] truncate border-[1px] border-base-content`}
                                                            key={index}
                                                            title={
                                                                !isDate
                                                                    ? (value?.toString() ??
                                                                      "")
                                                                    : (formattedDates(
                                                                          woTz(
                                                                              new Date(
                                                                                  value as string,
                                                                              ),
                                                                          ) as Date,
                                                                      ) ?? "")
                                                            }
                                                        >
                                                            {valuesToUnderline.includes(
                                                                key,
                                                            ) ? (
                                                                <span className="text-red-600 font-bold underline">
                                                                    {value !==
                                                                    ""
                                                                        ? value
                                                                        : "-"}
                                                                </span>
                                                            ) : (
                                                                formatValue(
                                                                    (value as string) ??
                                                                        "",
                                                                )
                                                            )}
                                                        </td>
                                                    );
                                                })}
                                            </tr>
                                        );
                                    },
                                );
                            });
                        })
                    )}
                </tbody>
            </table>
        </div>
    );
};

export default RinexTable;
