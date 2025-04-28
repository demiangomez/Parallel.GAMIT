import { useState, useEffect, useMemo } from "react";
import { Scroller, Spinner } from "@componentsReact";
import { useAuth, useApi, useLocalStorage } from "@hooks";
import { getStationStatusService, getStationTypesService } from "@services";
import {
    EarthQuakeFormState,
    FilterState,
    StationStatus,
    StationStatusServiceData,
} from "@types";

interface MainScrollerProps {
    mapState: boolean;
    topoMapState: boolean;
    altData?: {
        dataFiltered: any[];
        originalDataCount: any;
        hasEarthquakes?: boolean;
    };
    fromMain: boolean;
    filters: {
        openFilters: boolean;
        stationType: boolean;
        stationWithProblems: boolean;
        stationWithoutProblems: boolean;
        stationStatus: boolean;
    };
    filterState: FilterState;
    showScroller: boolean;
    setFilters: React.Dispatch<
        React.SetStateAction<{
            openFilters: boolean;
            stationType: boolean;
            stationWithProblems: boolean;
            stationWithoutProblems: boolean;
            stationStatus: boolean;
        }>
    >;
    setFormState: React.Dispatch<React.SetStateAction<EarthQuakeFormState>>;
    setFilterState: React.Dispatch<React.SetStateAction<FilterState>>;
    setTopoMapState: React.Dispatch<React.SetStateAction<boolean>>;
    setShowScroller: React.Dispatch<React.SetStateAction<boolean>>;
    setShowEarthquakeModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
}

const MainScroller = ({
    altData,
    mapState,
    filters,
    fromMain,
    filterState,
    topoMapState,
    showScroller,
    setFilters,
    setFormState,
    setFilterState,
    setTopoMapState,
    setShowScroller,
    setShowEarthquakeModal,
}: MainScrollerProps) => {
    //------------------------------------------------UseAuth----------------------------------------------
    const { token, logout } = useAuth();

    //------------------------------------------------UseApi----------------------------------------------
    const api = useApi(token, logout);

    //------------------------------------------------UseLocalStorage----------------------------------------------
    const [mapFilters, setMapFilters] = useLocalStorage(
        "mapFilters",
        JSON.stringify({}),
    );

    //------------------------------------------------UseState----------------------------------------------
    const [stationType, setStationType] = useState<StationStatus[]>([]);

    const [stationStatus, setStationStatus] = useState<StationStatus[]>([]);

    const [loading, setLoading] = useState<boolean>(false);

    //------------------------------------------------Functions----------------------------------------------
    const handleLocalStorage = (key: string, value: string) => {
        setMapFilters(
            JSON.stringify({
                ...JSON.parse(mapFilters ?? "{}"),
                [key]: value,
            }),
        );
    };

    const getTypes = async () => {
        try {
            setLoading(true);
            const status =
                await getStationStatusService<StationStatusServiceData>(api);

            const types =
                await getStationTypesService<StationStatusServiceData>(api);

            setStationType(types.data ?? []);
            setStationStatus(status.data ?? []);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const hasFilters = () => {
        return (
            filters.stationWithProblems ||
            filters.stationWithoutProblems ||
            filterState.typeOption?.length ||
            filterState.statusOption?.length
        );
    };

    const hasFilteredData =
        hasFilters() && altData?.dataFiltered && !altData.hasEarthquakes;

    //------------------------------------------------UseEffect----------------------------------------------
    useEffect(() => {
        if (mapFilters) {
            const localStorageFilters = JSON.parse(mapFilters);

            const f = Object.entries(localStorageFilters).reduce(
                (acc, [key, value]) => {
                    return {
                        ...acc,
                        [key]: JSON.parse(value as string),
                    };
                },
                {},
            ) as any;

            setTopoMapState(f.topoMapState);

            setFilters((prev) => ({
                ...prev,
                stationWithProblems: f.stationWithProblems,
                stationWithoutProblems: f.stationWithoutProblems,
            }));

            setFilterState((prev) => ({
                ...prev,
                typeOption: f.stationType ?? [],
                statusOption: f.stationStatus ?? [],
            }));
        }
    }, [mapFilters]);

    const getTypesCallback = useMemo(() => {
        if (!mapState) {
            return () => getTypes();
        }
        return () => {};
    }, [mapState]);

    useEffect(() => {
        getTypesCallback();
    }, [getTypesCallback]);

    //------------------------------------------------Return----------------------------------------------

    return (
        <>
            <Scroller
                fromMain={true}
                hasFilteredData={hasFilteredData && !mapState ? true : false}
                buttonCondition={true}
                scrollerCondition={fromMain && showScroller}
                scrollerName={
                    !mapState && hasFilteredData && altData?.originalDataCount
                        ? "Filtered " +
                          altData?.dataFiltered.length.toString() +
                          " from " +
                          altData?.originalDataCount
                        : "Options"
                }
                showScroller={showScroller}
                setShowScroller={setShowScroller}
            >
                {loading ? (
                    <div className="w-full flex justify-center py-4">
                        <Spinner size="lg" />
                    </div>
                ) : (
                    <ul className="menu rounded-box w-auto">
                        <li>
                            <div
                                className="form-control p-0"
                                onClick={() => {
                                    setShowEarthquakeModal({
                                        show: true,
                                        title: "earthquake",
                                        type: "none",
                                    });
                                    setFormState({
                                        date_start: undefined,
                                        date_end: undefined,
                                        max_magnitude: "",
                                        min_magnitude: "",
                                        id: "",
                                        max_depth: "",
                                        min_depth: "",
                                        min_latitude: "",
                                        max_latitude: "",
                                        min_longitude: "",
                                        max_longitude: "",
                                        polygon_coordinates: [[]],
                                    });
                                }}
                            >
                                <label className="label cursor-pointer truncate w-[370px]">
                                    <span className="font-bold mr-4">
                                        Find Earthquake
                                    </span>
                                    <svg
                                        xmlns="http://www.w3.org/2000/svg"
                                        fill="none"
                                        viewBox="0 0 24 24"
                                        strokeWidth={1.5}
                                        stroke="currentColor"
                                        className="size-6"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
                                        />
                                    </svg>
                                </label>
                            </div>
                        </li>
                        <li>
                            <div className="form-control p-0">
                                <label className="label cursor-pointer truncate w-[370px]">
                                    <span className="font-bold mr-4">
                                        Topo Layer
                                    </span>
                                    <input
                                        type="checkbox"
                                        className="checkbox checkbox-sm"
                                        defaultChecked={topoMapState}
                                        onChange={(e) => {
                                            handleLocalStorage(
                                                "topoMapState",
                                                e.target.checked.toString(),
                                            );
                                            setTopoMapState(e.target.checked);
                                        }}
                                    />
                                </label>
                            </div>
                        </li>
                        {!mapState && (
                            <li>
                                <details>
                                    <summary
                                        onClick={() => {
                                            setFilters((prev) => {
                                                return {
                                                    ...prev,
                                                    openFilters:
                                                        !prev.openFilters,
                                                };
                                            });
                                        }}
                                    >
                                        Filters
                                    </summary>
                                    <ul>
                                        <li>
                                            <div className="form-control">
                                                <label className="label cursor-pointer truncate w-[248px]">
                                                    <span className="font-bold mr-4 ">
                                                        Station With Problems
                                                    </span>
                                                    <input
                                                        type="checkbox"
                                                        className="checkbox checkbox-sm"
                                                        defaultChecked={
                                                            filters.stationWithProblems
                                                        }
                                                        onClick={() => {
                                                            handleLocalStorage(
                                                                "stationWithProblems",
                                                                (!filters.stationWithProblems).toString(),
                                                            );
                                                            setFilters(
                                                                (prev) => {
                                                                    return {
                                                                        ...prev,
                                                                        stationWithProblems:
                                                                            !prev.stationWithProblems,
                                                                    };
                                                                },
                                                            );
                                                        }}
                                                    />
                                                </label>
                                            </div>
                                        </li>
                                        <li>
                                            <div className="form-control">
                                                <label className="label cursor-pointer truncate w-[248px]">
                                                    <span className="font-bold mr-4 ">
                                                        Station Without Problems
                                                    </span>
                                                    <input
                                                        type="checkbox"
                                                        className="checkbox checkbox-sm"
                                                        defaultChecked={
                                                            filters.stationWithoutProblems
                                                        }
                                                        onClick={() => {
                                                            handleLocalStorage(
                                                                "stationWithoutProblems",
                                                                (!filters.stationWithoutProblems).toString(),
                                                            );
                                                            setFilters(
                                                                (prev) => {
                                                                    return {
                                                                        ...prev,
                                                                        stationWithoutProblems:
                                                                            !prev.stationWithoutProblems,
                                                                    };
                                                                },
                                                            );
                                                        }}
                                                    />
                                                </label>
                                            </div>
                                        </li>
                                        <li>
                                            <details>
                                                <summary
                                                    onClick={() => {
                                                        setFilters((prev) => {
                                                            return {
                                                                ...prev,
                                                                stationType:
                                                                    !prev.stationType,
                                                            };
                                                        });
                                                    }}
                                                >
                                                    Station type
                                                </summary>
                                                <ul>
                                                    {stationType.map(
                                                        (typeOption) => (
                                                            <li
                                                                key={
                                                                    typeOption.id
                                                                }
                                                            >
                                                                <div className="form-control">
                                                                    <label className="label cursor-pointer truncate w-[225px]">
                                                                        <span className="font-bold mr-4">
                                                                            {
                                                                                typeOption.name
                                                                            }
                                                                        </span>
                                                                        <input
                                                                            type="checkbox"
                                                                            className="checkbox checkbox-sm"
                                                                            defaultChecked={
                                                                                Array.isArray(
                                                                                    filterState.typeOption,
                                                                                ) &&
                                                                                filterState.typeOption.includes(
                                                                                    typeOption.name,
                                                                                )
                                                                            }
                                                                            onClick={(
                                                                                e,
                                                                            ) => {
                                                                                const target =
                                                                                    e.target as HTMLInputElement;

                                                                                handleLocalStorage(
                                                                                    "stationType",
                                                                                    filters.stationType.toString(),
                                                                                );

                                                                                target.checked
                                                                                    ? (handleLocalStorage(
                                                                                          "stationType",
                                                                                          JSON.stringify(
                                                                                              [
                                                                                                  ...(filterState.typeOption ||
                                                                                                      []),
                                                                                                  typeOption.name,
                                                                                              ],
                                                                                          ),
                                                                                      ),
                                                                                      setFilterState(
                                                                                          (
                                                                                              prev,
                                                                                          ) => ({
                                                                                              ...prev,
                                                                                              typeOption:
                                                                                                  [
                                                                                                      ...(prev.typeOption ||
                                                                                                          []),
                                                                                                      typeOption.name,
                                                                                                  ],
                                                                                          }),
                                                                                      ))
                                                                                    : (handleLocalStorage(
                                                                                          "stationType",
                                                                                          JSON.stringify(
                                                                                              filterState.typeOption?.filter(
                                                                                                  (
                                                                                                      option,
                                                                                                  ) =>
                                                                                                      option !==
                                                                                                      typeOption.name,
                                                                                              ),
                                                                                          ),
                                                                                      ),
                                                                                      setFilterState(
                                                                                          (
                                                                                              prev,
                                                                                          ) => ({
                                                                                              ...prev,
                                                                                              typeOption:
                                                                                                  prev.typeOption?.filter(
                                                                                                      (
                                                                                                          option,
                                                                                                      ) =>
                                                                                                          option !==
                                                                                                          typeOption.name,
                                                                                                  ),
                                                                                          }),
                                                                                      ));
                                                                            }}
                                                                        />
                                                                    </label>
                                                                </div>
                                                            </li>
                                                        ),
                                                    )}
                                                </ul>
                                            </details>
                                        </li>
                                        <li>
                                            <details>
                                                <summary
                                                    onClick={() => {
                                                        setFilters((prev) => {
                                                            return {
                                                                ...prev,
                                                                stationStatus:
                                                                    !prev.stationStatus,
                                                            };
                                                        });
                                                    }}
                                                >
                                                    Station Status
                                                </summary>
                                                <ul>
                                                    {stationStatus.map(
                                                        (statusOption) => (
                                                            <li
                                                                key={
                                                                    statusOption.id
                                                                }
                                                            >
                                                                <div className="form-control">
                                                                    <label className="label cursor-pointer truncate w-[225px]">
                                                                        <span className="font-bold mr-4">
                                                                            {
                                                                                statusOption.name
                                                                            }
                                                                        </span>
                                                                        <input
                                                                            type="checkbox"
                                                                            className="checkbox checkbox-sm"
                                                                            defaultChecked={
                                                                                Array.isArray(
                                                                                    filterState.statusOption,
                                                                                ) &&
                                                                                filterState.statusOption.includes(
                                                                                    statusOption.name,
                                                                                )
                                                                            }
                                                                            onClick={(
                                                                                e,
                                                                            ) => {
                                                                                const target =
                                                                                    e.target as HTMLInputElement;

                                                                                handleLocalStorage(
                                                                                    "stationStatus",
                                                                                    filterState?.statusOption?.toString(),
                                                                                );

                                                                                target.checked
                                                                                    ? (handleLocalStorage(
                                                                                          "stationStatus",
                                                                                          JSON.stringify(
                                                                                              [
                                                                                                  ...(filterState.statusOption ||
                                                                                                      []),
                                                                                                  statusOption.name,
                                                                                              ],
                                                                                          ),
                                                                                      ),
                                                                                      setFilterState(
                                                                                          (
                                                                                              prev,
                                                                                          ) => ({
                                                                                              ...prev,
                                                                                              statusOption:
                                                                                                  [
                                                                                                      ...(prev.statusOption ||
                                                                                                          []),
                                                                                                      statusOption.name,
                                                                                                  ],
                                                                                          }),
                                                                                      ))
                                                                                    : (handleLocalStorage(
                                                                                          "stationStatus",
                                                                                          JSON.stringify(
                                                                                              filterState.statusOption?.filter(
                                                                                                  (
                                                                                                      option,
                                                                                                  ) =>
                                                                                                      option !==
                                                                                                      statusOption.name,
                                                                                              ),
                                                                                          ),
                                                                                      ),
                                                                                      setFilterState(
                                                                                          (
                                                                                              prev,
                                                                                          ) => ({
                                                                                              ...prev,
                                                                                              statusOption:
                                                                                                  prev.statusOption?.filter(
                                                                                                      (
                                                                                                          option,
                                                                                                      ) =>
                                                                                                          option !==
                                                                                                          statusOption.name,
                                                                                                  ),
                                                                                          }),
                                                                                      ));
                                                                            }}
                                                                        />
                                                                    </label>
                                                                </div>
                                                            </li>
                                                        ),
                                                    )}
                                                </ul>
                                            </details>
                                        </li>
                                    </ul>
                                </details>
                            </li>
                        )}
                    </ul>
                )}
            </Scroller>
        </>
    );
};

export default MainScroller;
