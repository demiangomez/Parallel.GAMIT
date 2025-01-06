import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { LatLngExpression } from "leaflet";

import { ChevronLeftIcon } from "@heroicons/react/24/outline";

import {
    Map,
    MapSkeleton,
    SearchInput,
    Sidebar,
    Spinner,
    StationsModal,
    MainScroller,
    EarthQuakeFormModal,
    EarthQuakeScroller,
    DropLeft,
} from "@componentsReact";

import { useAuth, useApi, useEscape } from "@hooks";

import {
    getAffectedStationsService,
    getEarthquakesService,
    getStationsService,
} from "@services";

import { isStationFiltered, showModal } from "@utils";

import {
    GetParams,
    StationData,
    StationServiceData,
    FilterState,
    EarthQuakeFormState,
    EarthquakeData,
    EarthQuakeParams,
    StationsAffectedServiceData,
} from "@types";

const MainPage = () => {
    //---------------------------------------------------------UseAuth-------------------------------------------------------------
    const { token, logout } = useAuth();

    //---------------------------------------------------------UseApi-------------------------------------------------------------
    const api = useApi(token, logout);

    //---------------------------------------------------------UseLocation-------------------------------------------------------------
    const location = useLocation();

    //---------------------------------------------------------UseState-------------------------------------------------------------
    const [forceSyncScrollerMap, setForceSyncScrollerMap] = useState(0);

    const [earthQuakeAffectedParams, setEarthQuakeAffectedParams] = useState<
        number | undefined
    >(undefined);

    const [earthQuakeAffectedStations, setEarthQuakeAffectedStations] =
        useState<StationsAffectedServiceData | undefined>(undefined);

    const [chosenEarthquake, setChosenEarthquake] = useState<
        EarthquakeData | undefined
    >(undefined);

    const [forceSyncDropLeftMap, setForceSyncDropLeftMap] = useState(0);

    const [posToFly, setPosToFly] = useState<LatLngExpression | undefined>(
        undefined,
    );

    const [earthquakes, setEarthquakes] = useState<
        EarthquakeData[] | undefined
    >(undefined);

    const [station, setStation] = useState<StationData | undefined>(undefined);

    const [stations, setStations] = useState<StationData[] | undefined>(
        undefined,
    );

    const [initialStations, setInitialStations] = useState<
        StationData[] | undefined
    >(undefined);

    const [initialCenter, setInitialCenter] = useState<
        LatLngExpression | undefined
    >(undefined);

    const [formstate, setFormState] = useState<EarthQuakeFormState>({
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

    const [markersByBounds, setMarkersByBounds] = useState<
        StationData[] | EarthquakeData[] | undefined
    >(undefined);

    const [mapState, setMapState] = useState<boolean>(false);

    const [list, setList] = useState<boolean>(false);

    const [loading, setLoading] = useState<boolean>(true);

    const [spinner, setSpinner] = useState<boolean>(false);

    const [stationsUpdated, setStationsUpdated] = useState<boolean>(false);

    const [params, setParams] = useState<GetParams>({
        country_code: "",
        network_code: "",
        station_code: "",
        limit: 0,
        offset: 0,
    });

    const [earthquakeModal, setEarthquakeModal] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const [showScroller, setShowScroller] = useState(false);

    const [topoMapState, setTopoMapState] = useState(false);

    const [filterState, setFilterState] = useState<FilterState>({
        statusOption: [],
        typeOption: [],
    });

    const [filters, setFilters] = useState({
        openFilters: false,
        stationType: false,
        stationWithProblems: false,
        stationWithoutProblems: false,
        stationStatus: false,
    });

    const [showSidebar, setShowSidebar] = useState<boolean>(false);

    const [showEarthQuakesList, setShowEarthQuakesList] =
        useState<boolean>(false);

    const [earthQuakeParams, setEarthQuakeParams] = useState<
        EarthQuakeParams | undefined
    >(undefined);

    const [earthQuakeFiltered, setEarthQuakeFiltered] = useState<
        EarthquakeData[]
    >([]);

    //---------------------------------------------------------Constantes------------------------------------------------------------

    const windowState = window.history.state.usr as StationData;

    const locationState =
        location.state && windowState
            ? windowState
            : (location.state as StationData);

    //---------------------------------------------------------UseRef-------------------------------------------------------------

    const abortControllerRef = useRef<AbortController | null>(null);

    

    //---------------------------------------------------------Funciones-------------------------------------------------------------

    const getAffectedStations = async () => {
        try {
            setEarthQuakeAffectedStations(undefined);
            setSpinner(true);
            const result =
                await getAffectedStationsService<StationsAffectedServiceData>(
                    api,
                    earthQuakeAffectedParams,
                );
            if (result) {
                setEarthQuakeAffectedStations(result);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setSpinner(false);
        }
    };

    const getInitialStations = async () => {
        try {
            setLoading(true);
            const result = await getStationsService<StationServiceData>(
                api,
                params,
            );
            if (result) {
                setInitialStations(result.data);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const getEarthquakes = async () => {
        setSpinner(true);
        try {
            const res = await getEarthquakesService<any>(api, earthQuakeParams);
            
            const filteredEarthquakes =
                (Array.isArray(formstate?.polygon_coordinates) &&
                    formstate.polygon_coordinates[0].length > 0) ||
                !isEmpty(formstate?.max_latitude) ||
                !isEmpty(formstate?.min_latitude) ||
                !isEmpty(formstate?.max_longitude) ||
                !isEmpty(formstate?.min_longitude)
                    ? res.data?.filter((s: EarthquakeData) =>
                          isEarthquakeFiltered(s),
                      )
                    : res.data;

            setEarthquakes(filteredEarthquakes);
        } catch (err) {
            console.error(err);
        } finally {
            setSpinner(false);
        }
    };

        


    const getStations = async () => {
        setSpinner(true);

        // Cancel the previous request if it exists
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }

        // Create a new AbortController for the new request
        const abortController = new AbortController();
        abortControllerRef.current = abortController;

        try {
            const result = await getStationsService<StationServiceData>(
                api,
                params,
                { signal: abortController.signal },
            );
            if (result) {
                setStations(result.data);
                setStationsUpdated(true);
                if (result.data?.length > 0) {
                    result.data.find((s) => {
                        if (s.lat && s.lon) {
                            const hasEqualParams =
                                JSON.stringify(locationState?.mainParams) ===
                                JSON.stringify(params);

                            if (hasEqualParams) {
                                setInitialCenter([
                                    locationState?.lat,
                                    locationState?.lon,
                                ]);
                            } else {
                                setInitialCenter([s.lat, s.lon]);
                            }
                        }
                    });
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setSpinner(false);
        }
    };

    const isEmpty = (s: string | undefined) => {
        return s === "" || s === null || s === undefined;
    };

    const isEarthquakeFiltered = (earthquake: EarthquakeData | undefined) => {
        if (earthquake) {
            if (formstate) {
                if (
                    formstate.max_latitude ||
                    formstate.min_latitude ||
                    formstate.max_longitude ||
                    formstate.min_longitude
                ) {
                    return handleLimits(earthquake, formstate);
                }
            } else {
                return false;
            }
        }
    };

    const handleLimits = (
        earthquake: EarthquakeData,
        formState: EarthQuakeFormState,
    ) => {
        const { max_lattitude, min_lattitude, max_longitude, min_longitude } = {
            max_lattitude: Number(formState.max_latitude),
            min_lattitude: Number(formState.min_latitude),
            max_longitude: Number(formState.max_longitude),
            min_longitude: Number(formState.min_longitude),
        };

        if (max_lattitude && min_lattitude && max_longitude && min_longitude) {
            return (
                earthquake.lat <= max_lattitude &&
                earthquake.lat >= min_lattitude &&
                earthquake.lon <= max_longitude &&
                earthquake.lon >= min_longitude
            );
        } else if (max_lattitude && min_lattitude && max_longitude) {
            return (
                earthquake.lat <= max_lattitude &&
                earthquake.lat >= min_lattitude &&
                earthquake.lon <= max_longitude
            );
        } else if (max_lattitude && min_lattitude && min_longitude) {
            return (
                earthquake.lat <= max_lattitude &&
                earthquake.lat >= min_lattitude &&
                earthquake.lon >= min_longitude
            );
        } else if (max_lattitude && max_longitude && min_longitude) {
            return (
                earthquake.lat <= max_lattitude &&
                earthquake.lon <= max_longitude &&
                earthquake.lon >= min_longitude
            );
        } else if (min_lattitude && max_longitude && min_longitude) {
            return (
                earthquake.lat >= min_lattitude &&
                earthquake.lon <= max_longitude &&
                earthquake.lon >= min_longitude
            );
        } else if (max_lattitude && min_lattitude) {
            return (
                earthquake.lat <= max_lattitude &&
                earthquake.lat >= min_lattitude
            );
        } else if (max_longitude && min_longitude) {
            return (
                earthquake.lon <= max_longitude &&
                earthquake.lon >= min_longitude
            );
        } else if (max_lattitude && max_longitude) {
            return (
                earthquake.lat <= max_lattitude &&
                earthquake.lon <= max_longitude
            );
        } else if (max_lattitude && min_longitude) {
            return (
                earthquake.lat <= max_lattitude &&
                earthquake.lon >= min_longitude
            );
        } else if (min_lattitude && max_longitude) {
            return (
                earthquake.lat >= min_lattitude &&
                earthquake.lon <= max_longitude
            );
        } else if (min_lattitude && min_longitude) {
            return (
                earthquake.lat >= min_lattitude &&
                earthquake.lon >= min_longitude
            );
        } else if (max_lattitude) {
            return earthquake.lat <= max_lattitude;
        } else if (min_lattitude) {
            return earthquake.lat >= min_lattitude;
        } else if (max_longitude) {
            return earthquake.lon <= max_longitude;
        } else if (min_longitude) {
            return earthquake.lon >= min_longitude;
        }

        return false;
    };

    const handleEarthQuakeParams = (formstate: EarthQuakeFormState) => {
        setEarthQuakeParams({
            date_start: formstate.date_start
                ? formstate.date_start + ":00"
                : undefined,
            date_end: formstate.date_end
                ? formstate.date_end + ":00"
                : undefined,
            max_magnitude: formstate.max_magnitude
                ? parseFloat(formstate.max_magnitude)
                : undefined,
            min_magnitude: formstate.min_magnitude
                ? parseFloat(formstate.min_magnitude)
                : undefined,
            id: formstate.id ? formstate.id : undefined,
            max_depth: formstate.max_depth
                ? parseFloat(formstate.max_depth)
                : undefined,
            min_depth: formstate.min_depth
                ? parseFloat(formstate.min_depth)
                : undefined,
        });
    };

    const handleEarthquakes = () => {
        handleEarthQuakeParams(formstate);

        setChosenEarthquake(undefined);

        setEarthQuakeAffectedStations(undefined);

        setMapState(true);
    };

    const handleEarthquakeState = (earthquake: EarthquakeData) => {
        setPosToFly([earthquake.lat, earthquake.lon]);

        if (
            chosenEarthquake?.api_id !== earthquake.api_id ||
            chosenEarthquake === undefined
        ) {
            setEarthQuakeAffectedParams(earthquake.api_id);

            setChosenEarthquake(earthquake);
        } else if (chosenEarthquake?.api_id === earthquake.api_id) {
            setChosenEarthquake(undefined);

            setEarthQuakeAffectedParams(undefined);
        }
    };

    const stationsByFilters = (stations: StationData[]) => {
        const filteredStations =
            filters?.stationWithProblems ||
            filters?.stationWithoutProblems ||
            (Array.isArray(filterState?.statusOption) &&
                filterState?.statusOption.length > 0) ||
            (Array.isArray(filterState?.typeOption) &&
                filterState?.typeOption.length > 0)
                ? stations?.filter((s) =>
                      isStationFiltered(s, filterState, filters),
                  )
                : stations;

        return filteredStations;
    };

    const exitEarthquakes = () => {
        if (mapState) {
            setMapState(false);
            setShowEarthQuakesList(false);
            setEarthQuakeParams(undefined);
            setEarthQuakeFiltered([]);
            setChosenEarthquake(undefined);
        }
    };

    //---------------------------------------------------------UseEffect-------------------------------------------------------------
    useEffect(() => {
        if (earthQuakeAffectedParams && chosenEarthquake) {
            getAffectedStations();
        } else if (earthQuakeAffectedParams === undefined) {
            setEarthQuakeAffectedStations(undefined);
        }
    }, [chosenEarthquake]);

    useEffect(() => {
        if (mapState) {
            getEarthquakes();
        }
    }, [earthQuakeParams]);

    useEffect(() => {
        if (earthquakes) {
            setChosenEarthquake(undefined);

            setEarthQuakeFiltered(earthquakes);
        }
    }, [earthquakes]);

    useEffect(() => {
        if (
            (initialStations &&
                params.station_code === " " && // PARAMS RESETEADOS
                params.country_code === " " &&
                params.network_code === " ") ||
            (params.station_code === "" && // PARAMS RESETEADOS
                params.country_code === "" &&
                params.network_code === "")
        ) {
            abortControllerRef.current?.abort();
            setStations(initialStations);
            setInitialCenter(
                initialCenter
                    ? [
                          (initialCenter as [number, number])[0],
                          (initialCenter as [number, number])[1],
                      ]
                    : undefined,
            );
        }
        if (
            initialStations &&
            (params.country_code?.trim() !== "" ||
                params.network_code?.trim() !== "" ||
                params.station_code?.trim() !== "")
        ) {
            getStations();
        }
    }, [params]);

    useEffect(() => {
        if (stationsUpdated) {
            if (
                params.station_code === "" && // PARAMS RESETEADOS
                params.country_code === "" &&
                params.network_code === ""
            ) {
                setStations(initialStations);
            }

            setStationsUpdated(false); // Resetear el estado
        }
    }, [stationsUpdated]);

    useEffect(() => {
        const stateCoordinates =
            locationState !== null && Object.values(locationState).length > 0
                ? ([locationState?.lat, locationState?.lon] as LatLngExpression)
                : undefined;

        if (stateCoordinates) {
            setInitialCenter(stateCoordinates);
        }
    }, [locationState]);

    useEffect(() => {
        if (!initialStations) {
            // FIXME: Corresponder las initialstations al rango de la vista
            //que el usuario tenga determinada ??¿¿, seguro tenga que hacer un nuevo getStations
            getInitialStations();
        }
    }, []);

    useEffect(() => {
        earthquakeModal?.show && showModal(earthquakeModal.title);
    }, [earthquakeModal]);

    useEffect(() => {
        const earthquake: EarthquakeData | undefined = earthquakes
            ? earthquakes[0]
            : undefined;

        if (earthquake && chosenEarthquake === undefined) {
            setPosToFly([earthquake.lat, earthquake.lon]);
        }
    }, [earthquakes]);

    //---------------------------------------------------------UseEscape-------------------------------------------------------------

    useEscape(exitEarthquakes);

    return (
        <div
            className={
                "my-auto flex flex-1 transition-all duration-200 relative "
            }
        >
            {loading ? (
                <MapSkeleton />
            ) : (
                <>
                    <MainScroller
                        filters={filters}
                        fromMain={true}
                        filterState={filterState}
                        showScroller={showScroller}
                        topoMapState={topoMapState}
                        altData={{
                            dataFiltered: stationsByFilters(stations || []),
                            originalDataCount: stations?.length,
                            hasEarthquakes: showEarthQuakesList,
                        }}
                        setFilters={setFilters}
                        setFormState={setFormState}
                        setFilterState={setFilterState}
                        setTopoMapState={setTopoMapState}
                        setShowScroller={setShowScroller}
                        setShowEarthquakeModal={setEarthquakeModal}
                        mapState={mapState}
                    />

                    <EarthQuakeScroller
                        setScroll={setShowEarthQuakesList}
                        scrollerCondition={showEarthQuakesList}
                        earthquakes={earthquakes || []}
                        earthquakeChosen={chosenEarthquake}
                        setMapState={setMapState}
                        spinner={spinner}
                        handleEarthquakeState={handleEarthquakeState}
                        forceSyncMapScroller={forceSyncScrollerMap}
                    />

                    {earthquakeModal &&
                        earthquakeModal.title === "earthquake" && (
                            <EarthQuakeFormModal
                                formstate={formstate}
                                setInitialCenter={setInitialCenter}
                                setShowEarthquakeModal={setEarthquakeModal}
                                setFormState={setFormState}
                                handleEarthquakes={handleEarthquakes}
                                setShowEarthQuakesList={setShowEarthQuakesList}
                                setPosToFly={setPosToFly}
                            />
                        )}
                    {!mapState ? (
                        <Sidebar
                            show={showSidebar}
                            setShow={setShowSidebar}
                            station={station}
                        />
                    ) : null}
                    <div
                        className={"self-center w-full flex flex-col flex-wrap"}
                    >
                        <div
                            className={`absolute right-0 z-50 h-4/6 flex items-center`}
                        >
                            {" "}
                            {!mapState && (
                                <button
                                    className="btn"
                                    style={{
                                        writingMode: "vertical-rl",
                                        width: "50px",
                                        height: "200px",
                                        fontSize: "18px",
                                    }}
                                    onClick={() => {
                                        setList(!list);
                                    }}
                                >
                                    {" "}
                                    Station lists
                                    <ChevronLeftIcon className="h-6 w-6" />
                                </button>
                            )}
                        </div>
                        <div className="flex justify-center flex-wrap items-center absolute z-[12] w-full top-8">
                            {!mapState && (
                                <SearchInput
                                    stations={stations}
                                    params={params}
                                    setParams={setParams}
                                    setStation={setStation}
                                />
                            )}
                        </div>
                        {spinner && (
                            <div className="absolute mt-28 right-52 z-50">
                                {" "}
                                <Spinner size={"lg"} />
                            </div>
                        )}
                        {mapState && (
                            <DropLeft
                                mapState={showEarthQuakesList}
                                setMapState={setShowEarthQuakesList}
                                setForceSyncDropLeftMap={
                                    setForceSyncDropLeftMap
                                }
                            />
                        )}
                        <Map
                            stations={stations ? stations : initialStations}
                            initialCenter={initialCenter}
                            mainParams={params}
                            topoMap={topoMapState}
                            filters={filters}
                            filterState={filterState}
                            mapState={mapState}
                            markersByBounds={markersByBounds}
                            setMarkersByBounds={setMarkersByBounds}
                            earthquakesFiltered={earthQuakeFiltered || []}
                            setEarthquakesFiltered={setEarthQuakeFiltered}
                            earthquakes={earthquakes ? earthquakes : []}
                            handleEarthquakeState={handleEarthquakeState}
                            posToFly={posToFly}
                            earthquakeAffectedStations={
                                earthQuakeAffectedStations
                            }
                            earthQuakeChosen={chosenEarthquake}
                            setForceSyncScrollerMap={setForceSyncScrollerMap}
                            showEarthquakeList={showEarthQuakesList}
                            forceSyncDropLeftMap={forceSyncDropLeftMap}
                        />

                        {list && (
                            <div
                                className={`fixed right-20   
                                transition-all mt-[88px] h-fit flex z-50 `}
                            >
                                <StationsModal
                                    setState={setList}
                                    stations={stations}
                                    mainParams={params}
                                />
                            </div>
                        )}
                    </div>
                </>
            )}
        </div>
    );
};

export default MainPage;
