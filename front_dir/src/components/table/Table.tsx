import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Spinner } from "@componentsReact";

import { findFlagUrlByIso3Code } from "country-flags-svg-v2";

import { TrashIcon } from "@heroicons/react/24/outline";

import { formattedDates } from "@utils";
import { StationVisitsData } from "@types";

interface TableProps {
    table: string;
    loading?: boolean;
    dataOnly?: boolean;
    buttonRegister?: boolean;
    deleteRegister?: boolean;
    titles: string[];
    body: any[][] | undefined;
    alterInfo?: any;
    state?: any;
    setState?: any;
    onAlterClickFunction?: () => void;
    onClickFunction: () => void;
}

const Table = ({
    table,
    loading,
    dataOnly,
    buttonRegister,
    deleteRegister,
    titles,
    body,
    alterInfo,
    state,
    onClickFunction,
    onAlterClickFunction,
    setState,
}: TableProps) => {
    const navigate = useNavigate();

    const [visibleTooltipIndex, setVisibleTooltipIndex] = useState<
        number | null
    >(null);

    return (
        <div
            className={
                visibleTooltipIndex === null ? `overflow-x-auto pb-2` : ""
            }
        >
            <table className="table table-zebra bg-neutral-content">
                {table === "Station" && (
                    <caption className="py-2 truncate text-base-content text-[13px] font-light text-start">
                        RX as Receiver, ANT as Antenna, HC as Height Code, RAD
                        as Radome Code
                    </caption>
                )}

                <thead className="">
                    <tr>
                        {titles.length > 0 ? (
                            <>
                                {!dataOnly && !deleteRegister && (
                                    <th className="text-center text-neutral">
                                        Modify
                                    </th>
                                )}
                                {dataOnly && deleteRegister && (
                                    <th className="text-center text-neutral"></th>
                                )}
                                {buttonRegister && (
                                    <th className="text-center text-neutral">
                                        Add Visit
                                    </th>
                                )}
                            </>
                        ) : (
                            <th className="text-center text-neutral text-2xl">
                                {table === "People"
                                    ? "There are no people associated to this station"
                                    : `There is no information for this ${table}`}
                            </th>
                        )}

                        {titles.map((title, index) => (
                            <th
                                className="text-center text-neutral max-w-[200px]"
                                key={index}
                            >
                                {title
                                    ? title
                                          ?.toUpperCase()
                                          .replace(/_/g, " ")
                                          .replace("ANTENNA", "ANT")
                                          .replace("RECEIVER", "RX")
                                          .replace("RX FIRMWARE", "RX FW")
                                          .replace("HEIGHT CODE", "HC")
                                          .replace("RADOME CODE", "RAD")
                                          .replace(
                                              /ANT (HEIGHT|NORTH|EAST)/g,
                                              "$1",
                                          )
                                    : ""}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody className="">
                    {loading ? (
                        <tr>
                            <td
                                colSpan={titles.length + 1}
                                className="relative h-[200px]"
                            >
                                <div className="absolute inset-0 flex justify-center items-center">
                                    <Spinner size="lg" />
                                </div>
                            </td>
                        </tr>
                    ) : (
                        body?.map((row, index) => (
                            <tr
                                key={index + 1}
                                className={`${dataOnly && "cursor-pointer hover"}`}
                            >
                                {!dataOnly && !deleteRegister ? (
                                    <td key={index} className="text-center">
                                        <button
                                            className="btn btn-sm btn-circle btn-ghost"
                                            onClick={() => {
                                                onClickFunction();
                                                setState(state?.[index]);
                                            }}
                                        >
                                            📝
                                        </button>
                                    </td>
                                ) : (
                                    dataOnly &&
                                    deleteRegister && (
                                        <td key={index} className="text-center">
                                            <button
                                                className="btn btn-sm btn-square btn-ghost"
                                                onClick={() => {
                                                    onClickFunction();
                                                    setState(state?.[index]);
                                                }}
                                            >
                                                <TrashIcon className="size-6 text-red-600" />
                                            </button>
                                        </td>
                                    )
                                )}
                                {buttonRegister && (
                                    <td
                                        key={index + "add_visit"}
                                        className="text-center"
                                    >
                                        <button
                                            className="btn btn-sm btn-circle btn-ghost"
                                            onClick={() => {
                                                onAlterClickFunction &&
                                                    onAlterClickFunction();
                                                setState(state?.[index]);
                                            }}
                                        >
                                            Add
                                        </button>
                                    </td>
                                )}
                                {row.map(
                                    (
                                        val: string | boolean | number,
                                        idx: number,
                                    ) => {
                                        const isDateFunc = (val: any) => {
                                            const isoDateRegex =
                                                /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$/;
                                            return (
                                                typeof val === "string" &&
                                                isoDateRegex.test(val)
                                            );
                                        };
                                        const isDate =
                                            isDateFunc(val) && val !== "";
                                        
                                        const flag =
                                            titles[idx] === "country_code" &&
                                            val &&
                                            findFlagUrlByIso3Code(
                                                val as string,
                                            );

                                        const base64Str =
                                            "data:image/png;base64,";

                                        return (
                                            <td
                                                key={idx}
                                                title={
                                                    titles[idx] !== "Visit"
                                                        ? isDate
                                                            ? formattedDates(
                                                                  new Date(
                                                                      val as string,
                                                                  ),
                                                              )
                                                            : (String(val) ??
                                                              "")
                                                        : ""
                                                }
                                                className={`text-center max-w-[200px] overflow-visible text-ellipsis whitespace-nowrap
                                                    ${
                                                        titles[idx] ===
                                                            "country_code" &&
                                                        "flex justify-center"
                                                    }
                                                    ${
                                                        row?.[idx] === false
                                                            ? "text-red-600"
                                                            : row?.[idx] ===
                                                                  true &&
                                                              "text-green-600"
                                                    }
                                                        `}
                                                onClick={() => {
                                                    dataOnly &&
                                                        table === "Stations" &&
                                                        navigate(
                                                            `/${state?.[index].network_code}/${state?.[index].station_code}`,
                                                            {
                                                                state: {
                                                                    station:
                                                                        state?.[
                                                                            index
                                                                        ],
                                                                    mainParams:
                                                                        alterInfo,
                                                                },
                                                            },
                                                        );
                                                }}
                                            >
                                                {titles[idx] === "Color" && val && (
                                                    <div className="flex justify-center">
                                                        <div className={val as string} style={{width: '40px', height: '40px', backgroundColor: '#000', borderRadius: '50%'}}></div>
                                                    </div>
                                                )}
                                                {titles[idx] === "comments" && val && (
                                                    <div className="overflow-y-auto overflow-x-auto pl-8 max-h-32"
                                                        dangerouslySetInnerHTML={{
                                                            __html: val ?? "",
                                                        }}
                                                    />
                                                )}
                                                {titles[idx] === "country_code" && val && (
                                                    <img
                                                        width={30}
                                                        height={30}
                                                        className="mr-2"
                                                        src={`${flag}`}
                                                    />
                                                )}
                                                {titles[idx] === "Image" && val && (
                                                    <div className="avatar">
                                                        <div className="w-14 mask mask-squircle ">
                                                            <img
                                                                src={
                                                                    base64Str +
                                                                    val
                                                                }
                                                            />
                                                        </div>
                                                    </div>
                                                )
                                                }
                                                

                                                {val !== "" &&
                                                titles[idx] !== "Photo" &&
                                                titles[idx] !== "Visit" &&
                                                titles[idx] !== "comments" && 
                                                titles[idx] !== "Image" &&
                                                titles[idx] !== "Color"
                                                ? (
                                                    typeof val === "string" && titles[idx] !== "Image"  && titles[idx] !== "Color" ?  (
                                                        <div className="overflow-hidden text-ellipsis">
                                                            {val?.length > 15 &&
                                                            !isDate ? (
                                                                val?.substring(
                                                                    0,
                                                                    15,
                                                                ) + "..."
                                                            ) : isDate ? (
                                                                formattedDates(
                                                                    new Date(val),
                                                                )
                                                            ) : (
                                                                val
                                                            )}
                                                        </div>
                                                    ) : typeof val ===
                                                      "boolean" ? (
                                                        val ? (
                                                            "✔"
                                                        ) : (
                                                            "✘"
                                                        )
                                                    ) : typeof val ===
                                                      "number" ? (
                                                        val
                                                    ) : 
                                                    (
                                                        "-"
                                                    )
                                                ) : val !== "" &&
                                                  val !== null &&
                                                   titles[idx] === "Photo" ?(
                                                    <div className="avatar">
                                                        <div className="w-14 mask mask-squircle ">
                                                            <img
                                                                src={
                                                                    base64Str +
                                                                    val
                                                                }
                                                            />
                                                        </div>
                                                    </div>
                                                ) : val !== "" &&
                                                  val !== null &&
                                                  typeof val === "string"  &&
                                                  titles[idx] === "Visit" ? (
                                                    <div
                                                        className="relative group"
                                                        onMouseEnter={() =>
                                                            setVisibleTooltipIndex(
                                                                index,
                                                            )
                                                        }
                                                        onMouseLeave={() =>
                                                            setVisibleTooltipIndex(
                                                                null,
                                                            )
                                                        }
                                                    >   
                                                        <div>
                                                            {val?.length > 15 &&
                                                            !isDate
                                                                ? val?.substring(
                                                                      0,
                                                                      15,
                                                                  ) + "..."
                                                                : val}
                                                        </div>
                                                        {alterInfo && 
                                                            table !==
                                                                "Stations" && (
                                                                <div
                                                                    className={`absolute -translate-x-2/4 left-[50%] top-auto bottom-6 ${
                                                                        visibleTooltipIndex ===
                                                                        index
                                                                            ? "block"
                                                                            : "hidden"
                                                                    } bg-gray-800 text-white p-2 rounded 
                                                            text-pretty whitespace-nowrap w-[200px] z-50 overflow-visible`}
                                                                    onMouseEnter={() =>
                                                                        setVisibleTooltipIndex(
                                                                            index,
                                                                        )
                                                                    }
                                                                    onMouseLeave={() =>
                                                                        setVisibleTooltipIndex(
                                                                            null,
                                                                        )
                                                                    }
                                                                >
                                                                    {alterInfo?.[
                                                                        `${state?.[index].name}/~/${state?.[index].id}`
                                                                    ]?.map(
                                                                        (
                                                                            v: StationVisitsData,
                                                                        ) => {
                                                                            const stationNetwork =
                                                                                v?.station_formatted?.split(
                                                                                    ".",
                                                                                )[0];
                                                                            const stationCode =
                                                                                v?.station_formatted?.split(
                                                                                    ".",
                                                                                )[1];
                                                                            return (
                                                                                <Link
                                                                                    className="text-base block mb-1 even:bg-gray-700 rounded last:mb-0"
                                                                                    key={
                                                                                        v.id
                                                                                    }
                                                                                    to={`/${stationNetwork}/${stationCode}/visits`}
                                                                                    state={{
                                                                                        visitDetail:
                                                                                            v,
                                                                                    }}
                                                                                >
                                                                                    {" " +
                                                                                        "(" +
                                                                                        v.station_formatted +
                                                                                        ")" +
                                                                                        " - " +
                                                                                        v.date}{" "}
                                                                                </Link>
                                                                            );
                                                                        },
                                                                    )}
                                                                    <div
                                                                        className="absolute top-[100%] left-2/4 w-0 
                                                            -translate-x-2/4 h-0 border-l-8 border-l-transparent 
                                                            border-r-8 border-r-transparent border-t-8
                                                             border-t-gray-800"
                                                                    ></div>
                                                                </div>
                                                            )}
                                                    </div>
                                                ) : (titles[idx] !== "comments" && titles[idx] !== "Image" && titles[idx] !== "Color") ? (
                                                    "-"
                                                ) : null}
                                            </td>
                                        );
                                    },
                                )}
                            </tr>
                        ))
                    )}
                </tbody>
            </table>
        </div>
    );
};

export default Table;
