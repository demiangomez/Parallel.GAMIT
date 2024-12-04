import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { LatLngExpression } from "leaflet";
import {
    Map,
    MapSkeleton,
    SearchInput,
    Sidebar,
    Spinner,
    StationsModal,
} from "@componentsReact";

import useApi from "@hooks/useApi";
import { useAuth } from "@hooks/useAuth";

import { getStationsService } from "@services";
import { ChevronLeftIcon } from "@heroicons/react/24/outline";
import { GetParams, StationData, StationServiceData } from "@types";

const MainPage = () => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const location = useLocation();

    const windowState = window.history.state.usr as StationData;

    const locationState =
        location.state && windowState
            ? windowState
            : (location.state as StationData);

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

    const [list, setList] = useState<boolean>(false);

    const [loading, setLoading] = useState<boolean>(true);
    const [spinner, setSpinner] = useState<boolean>(false);
    const [stationsUpdated, setStationsUpdated] = useState<boolean>(false);

    const abortControllerRef = useRef<AbortController | null>(null);

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
            // if (!params.country_code || !params.network_code) return;
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

    const [showSidebar, setShowSidebar] = useState<boolean>(false);

    const [params, setParams] = useState<GetParams>({
        country_code: "",
        network_code: "",
        station_code: "",
        limit: 0,
        offset: 0,
    });

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
                    <Sidebar
                        show={showSidebar}
                        setShow={setShowSidebar}
                        station={station}
                    />
                    <div
                        className={"self-center w-full flex flex-col flex-wrap"}
                    >
                        <div
                            className={`absolute right-0 z-50 h-4/6 flex items-center`}
                        >
                            {" "}
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
                            </button>{" "}
                        </div>
                        <div className="flex justify-center flex-wrap items-center absolute z-50 w-full top-8">
                            <SearchInput
                                stations={stations}
                                params={params}
                                setParams={setParams}
                                setStation={setStation}
                            />
                        </div>
                        {spinner && (
                            <div className="absolute mt-28 right-52 z-50">
                                {" "}
                                <Spinner size={"lg"} />
                            </div>
                        )}
                        <Map
                            stations={stations ? stations : initialStations}
                            initialCenter={initialCenter}
                            mainParams={params}
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
