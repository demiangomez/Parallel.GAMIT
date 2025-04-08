import { useState, useEffect, useCallback } from "react";
import { Spinner } from "@componentsReact";

// import { ArrowDownTrayIcon, ClipboardIcon } from "@heroicons/react/24/outline";

import { formattedDates } from "@utils";

import { EarthquakeData } from "@types";

interface EarthQuakeScrollerProps {
    forceSyncMapScroller: number;
    earthquakes: EarthquakeData[];
    earthquakeChosen: EarthquakeData | undefined;
    handleEarthquakeState: (earthquake: EarthquakeData) => void;
    handleEarthquakeClose: () => void;
    scrollerCondition: boolean;
    spinner: boolean;
}

const EarthQuakeScroller: React.FC<EarthQuakeScrollerProps> = ({
    forceSyncMapScroller,
    earthquakes,
    earthquakeChosen,
    handleEarthquakeState,
    handleEarthquakeClose,
    spinner,
    scrollerCondition,
}) => {
    //---------------------------------------------------------UseState-------------------------------------------------------------
    const [forceRenderContainer, setForceRenderContainer] = useState(0);

    const [sortedEarthquakes, setSortedEarthquakes] = useState<
        EarthquakeData[]
    >([]);

    //---------------------------------------------------------Funciones-------------------------------------------------------------
    const isStateTrue = (earthquake: EarthquakeData) => {
        if (earthquakeChosen?.api_id === earthquake.api_id) {
            return true;
        }
        return false;
    };

    //---------------------------------------------------------UseCallback-------------------------------------------------------------
    const sortEarthquakes = useCallback(
        (sortBy: string) => {
            const newSorted = [...earthquakes];
            if (sortBy === "date-") {
                newSorted.sort(
                    (a, b) =>
                        new Date(a.date).getTime() - new Date(b.date).getTime(),
                );
            } else if (sortBy === "date+") {
                newSorted.sort(
                    (a, b) =>
                        new Date(b.date).getTime() - new Date(a.date).getTime(),
                );
            } else if (sortBy === "mag+") {
                newSorted.sort((a, b) => b.mag - a.mag);
            } else if (sortBy === "depth+") {
                newSorted.sort((a, b) => b.depth - a.depth);
            }
            setSortedEarthquakes(newSorted);
        },
        [earthquakes],
    );

    //---------------------------------------------------------UseEffect-------------------------------------------------------------
    useEffect(() => {
        setForceRenderContainer((prev) => prev + 1);
    }, [earthquakeChosen, sortedEarthquakes]);

    useEffect(() => {
        setSortedEarthquakes(earthquakes);
    }, [earthquakes]);

    //---------------------------------------------------------Return-------------------------------------------------------------

    return (
        <>
            {scrollerCondition ? (
                <div
                    id="controller"
                    className="z-[100000] max-h-[92vh] w-[20vw] scrollbar-thin overflow-y-auto overflow-x-hidden absolute top-0 left-0"
                >
                    <div className="overflow-y-auto min-h-[92vh] max-h-full h-auto bg-white rounded-md border-t border-l border-b border-gray-400 overflow-x-hidden">
                        {spinner ? (
                            <div className="flex items-center justify-center min-h-[92vh]">
                                <Spinner size="lg" />
                            </div>
                        ) : (
                            <div className="flex justify-end mr-2">
                                <svg
                                    xmlns="http://www.w3.org/2000/svg"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    strokeWidth={1.5}
                                    stroke="currentColor"
                                    className="size-6 cursor-pointer mt-2 mr-1 hover:bg-gray-200 hover:rounded-full hover:shadow-md"
                                    onClick={() => {
                                        handleEarthquakeClose();
                                    }}
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        d="M6 18 18 6M6 6l12 12"
                                    />
                                </svg>
                            </div>
                        )}
                        {!spinner && (
                            <div className="flex justify-between mb-3 mr-3 ml-3">
                                <div className="">
                                    <div className="font-bold text-xl">
                                        <h2>Search results</h2>
                                    </div>
                                    <div className="">
                                        {earthquakes.length + " earthquakes."}
                                    </div>
                                </div>
                                <div className="flex justify-center items-start flex-col">
                                    <div>
                                        <span>Sort by</span>
                                    </div>
                                    <div>
                                        <select
                                            className="border bg-white border-gray-400 rounded-md p-1"
                                            onChange={(e) =>
                                                sortEarthquakes(e.target.value)
                                            }
                                        >
                                            <option value="none">
                                                Select an option
                                            </option>
                                            <option value="date+">
                                                Newest
                                            </option>
                                            <option value="date-">
                                                Oldest
                                            </option>
                                            <option value="mag+">
                                                Magnitude
                                            </option>
                                            <option value="depth+">
                                                Depth
                                            </option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                        )}
                        {!spinner &&
                            sortedEarthquakes
                                ?.sort((a, b) => {
                                    const aState = isStateTrue(a);
                                    const bState = isStateTrue(b);
                                    if (aState && !bState) return -1;
                                    if (!aState && bState) return 1;
                                    return 0;
                                })
                                .map((earthquake) => (
                                    <div
                                        key={
                                            forceRenderContainer +
                                            earthquake.api_id +
                                            forceSyncMapScroller
                                        }
                                        onClick={() => {
                                            handleEarthquakeState(earthquake);
                                        }}
                                        className={
                                            isStateTrue(earthquake)
                                                ? "label cursor-pointer border border-gray-950 bg-slate-400 flex items-center justify-start flex-row p-2"
                                                : "label cursor-pointer border border-gray-400 flex items-center justify-start flex-row p-2"
                                        }
                                        id={earthquake.api_id.toString()}
                                    >
                                        <div className="flex items-start gap-4 m-2 mr-6">
                                            <div>{earthquake.mag}</div>
                                            <div className="flex flex-col">
                                                <span className="font-bold mr-2 break-words">
                                                    {earthquake.location}
                                                </span>
                                                <div>
                                                    <span className="mr-2 truncate">
                                                        {formattedDates(
                                                            earthquake.date,
                                                        )}
                                                    </span>
                                                    <span>
                                                        {earthquake.depth +
                                                            "km"}
                                                    </span>
                                                </div>
                                                <div>
                                                    <span>{earthquake.id}</span>
                                                </div>
                                                {/* {isStateTrue(earthquake) ? (
                                                    <div className="mt-4">
                                                        <div>
                                                            <span className="font-bold">
                                                                Masks
                                                            </span>
                                                            <div className="grid grid-cols-2 gap-4">
                                                                <div className="flex flex-col items-center justify-center">
                                                                    <span className="font-semibold text-sm">
                                                                        Coseismic
                                                                    </span>
                                                                    <button
                                                                        className="btn btn-ghost btn-circle"
                                                                        onClick={(
                                                                            e,
                                                                        ) => {
                                                                            e.stopPropagation();
                                                                            console.log(
                                                                                "Coseismic",
                                                                            );
                                                                        }}
                                                                    >
                                                                        <ArrowDownTrayIcon className="size-6" />
                                                                    </button>
                                                                </div>
                                                                <div className="flex flex-col items-center justify-center">
                                                                    <span className="font-semibold text-sm">
                                                                        Postseismic
                                                                    </span>
                                                                    <button
                                                                        className="btn btn-ghost btn-circle"
                                                                        onClick={(
                                                                            e,
                                                                        ) => {
                                                                            e.stopPropagation();
                                                                            console.log(
                                                                                "Coseismic",
                                                                            );
                                                                        }}
                                                                    >
                                                                        <ArrowDownTrayIcon className="size-6" />
                                                                    </button>
                                                                </div>
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <span className="font-bold">
                                                                Stations
                                                                Affected
                                                            </span>
                                                            <div className="grid grid-cols-2 gap-4 justify-items-center">
                                                                <button
                                                                    className="btn btn-ghost btn-circle"
                                                                    onClick={(
                                                                        e,
                                                                    ) => {
                                                                        e.stopPropagation();
                                                                    }}
                                                                >
                                                                    <ArrowDownTrayIcon className="size-6" />
                                                                </button>

                                                                <button
                                                                    className="btn btn-ghost btn-circle"
                                                                    onClick={(
                                                                        e,
                                                                    ) => {
                                                                        e.stopPropagation();
                                                                    }}
                                                                >
                                                                    <ClipboardIcon className="size-6" />
                                                                </button>
                                                            </div>
                                                        </div>
                                                    </div>
                                                ) : null} */}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                    </div>
                </div>
            ) : null}
        </>
    );
};
export default EarthQuakeScroller;
