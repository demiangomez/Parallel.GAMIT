import {
    NavigationType,
    Outlet,
    useLocation,
    useNavigate,
    useParams,
} from "react-router-dom";

import { useEffect, useMemo, useState } from "react";

import {
    Sidebar,
    Skeleton,
    Breadcrumb,
    PdfContainer,
    Toast,
} from "@componentsReact";
import { router } from "App";

import {
    ArrowPathIcon,
    ExclamationCircleIcon,
} from "@heroicons/react/24/outline";

import { useAuth } from "@hooks/useAuth";

import useApi from "@hooks/useApi";
import { generateErrorMessages, hasDifferences } from "@utils";

import {
    getStationImagesService,
    getStationMetaService,
    getStationsService,
    getStationVisitsService,
} from "@services";

import {
    Errors,
    StationData,
    StationImagesData,
    StationImagesServiceData,
    StationMetadataServiceData,
    StationServiceData,
    StationVisitsData,
    StationVisitsServiceData,
} from "@types";
import { AxiosError } from "axios";

const Station = () => {
    const { sc, nc } = useParams<{ sc: string; nc: string }>();
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [message, setMessage] = useState<{
        error: boolean | undefined;
        msg: string;
        errors?: Errors;
    }>({ error: undefined, msg: "", errors: undefined });

    const [station, setStation] = useState<StationData | undefined>(undefined);
    const [reStation, setReStation] = useState<StationData | undefined>(
        undefined,
    );

    const [stationMeta, setStationMeta] = useState<
        StationMetadataServiceData | undefined
    >(undefined);

    const [images, setImages] = useState<StationImagesData[] | undefined>(
        undefined,
    );

    const [visitForKml, setVisitForKml] = useState<
        StationVisitsData | undefined
    >(undefined);

    const [visits, setVisits] = useState<StationVisitsData[] | undefined>(
        undefined,
    );

    const [loading, setLoading] = useState<boolean>(true);
    const [reLoading, setReLoading] = useState<boolean>(false);
    const [photoLoading, setPhotoLoading] = useState<boolean>(true);

    const [stationLocationScreen, setStationLocationScreen] =
        useState<string>("");

    const [stationLocationDetailScreen, setStationLocationDetailScreen] =
        useState<string>("");

    const [loadPdf, setLoadPdf] = useState<boolean>(false);
    const [loadedMap, setLoadedMap] = useState<boolean | undefined>(undefined);

    const getStation = async () => {
        try {
            setLoading(true);
            const res = await getStationsService<StationServiceData>(api, {
                network_code: nc,
                station_code: sc,
                limit: 1,
                offset: 0,
            });
            setStation(res.data[0]);
        } catch (e) {
            console.error(e);
        }
    };

    const getReStation = async () => {
        try {
            setReLoading(true);
            closeToast();
            const res = await getStationsService<StationServiceData>(api, {
                network_code: nc,
                station_code: sc,
                limit: 1,
                offset: 0,
            });
            setReStation(res.data[0]);
            setMessage({
                error: false,
                msg: "Station refetched successfully",
            });
        } catch (error: unknown) {
            if (error instanceof AxiosError) {
                const apiErrorResponse = error.response?.data as Errors;
                setMessage({
                    error: true,
                    msg: error.message,
                    errors: apiErrorResponse,
                });
                console.error(error);
            }
        } finally {
            setReLoading(false);
        }
    };

    const getStationMeta = async () => {
        try {
            const res = await getStationMetaService<StationMetadataServiceData>(
                api,
                Number(station?.api_id),
            );
            if (res) {
                setStationMeta(res);
            }
        } catch (err) {
            console.error(err);
        }
    };

    const getStationImages = async () => {
        try {
            setPhotoLoading(true);
            const result =
                await getStationImagesService<StationImagesServiceData>(api, {
                    offset: 0,
                    limit: 0,
                    station_api_id: String(station?.api_id),
                });

            if (result) {
                setImages(result.data);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setPhotoLoading(false);
        }
    };

    const getVisits = async () => {
        try {
            const res = await getStationVisitsService<StationVisitsServiceData>(
                api,
                {
                    limit: 0,
                    offset: 0,
                    station_api_id: String(station?.api_id),
                },
            );

            if (res.statusCode === 200) {
                setVisitForKml(
                    res.data.sort(
                        (a, b) =>
                            new Date(b.date).getTime() -
                            new Date(a.date).getTime(),
                    )[0],
                );
                setVisits(res.data);
            }
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const refetch = () => {
        getStation();
        setLoadedMap(undefined);
    };

    const closeToast = () => {
        setMessage({ error: undefined, msg: "" });
    };

    const location = useLocation();

    const [showSidebar, setShowSidebar] = useState<boolean>(false);

    const locationState = location.state as StationData;

    const getButtonClasses = () => {
        const baseClasses = "hover:scale-110 btn-ghost rounded-lg p-1";
        let additionalClasses = "";

        if (
            location.pathname !== `/${nc}/${sc}` &&
            location.pathname !== `/${nc}/${sc}/rinex`
        ) {
            additionalClasses = "mr-8";
        } else if (location.pathname === `/${nc}/${sc}`) {
            additionalClasses = "mr-0";
        } else if (
            errorMessages.length === 0 &&
            location.pathname === `/${nc}/${sc}/rinex`
        ) {
            additionalClasses = "mr-8";
        } else if (
            errorMessages.length > 0 &&
            location.pathname === `/${nc}/${sc}/rinex`
        ) {
            additionalClasses = "mr-2";
        }

        return `${baseClasses} ${additionalClasses}`;
    };

    useEffect(() => {
        if (locationState && !loading) {
            setStation(locationState);
        } else {
            getStation();
        }
    }, [locationState]); //eslint-disable-line

    useEffect(() => {
        if (station) {
            getVisits();
            getStationMeta();
            getStationImages();
        }
    }, [station]); //eslint-disable-line

    const navigate = useNavigate();

    useEffect(() => {
        if (station) {
            const unsubscribe = router.subscribe((state) => {
                if (state.historyAction === NavigationType.Pop) {
                    if (state.location.pathname === "/") {
                        navigate("/temp", { replace: true, state: {} });
                        setTimeout(() => {
                            navigate("/", {
                                state: {
                                    ...locationState,
                                    mainParams:
                                        locationState.mainParams ?? undefined,
                                },
                            });
                        }, 0);
                    }
                }
            });

            return () => {
                unsubscribe();
            };
        }
    }, [station, locationState, navigate]);

    useEffect(() => {
        if (station) {
            if (location.pathname === `/${nc}/${sc}`) {
                getVisits();
            }
            setLoadPdf(false);
            setLoadedMap(undefined);
        }
    }, [location, station]);

    const stationTitle = station
        ? station?.network_code?.toUpperCase() +
          "." +
          station?.station_code?.toUpperCase()
        : "Station not found";

    const errorMessages = useMemo(() => {
        if (station && reStation && hasDifferences(station, reStation)) {
            return generateErrorMessages(reStation);
        } else if (station) {
            return generateErrorMessages(station);
        }
        return [];
    }, [station, reStation]);

    return (
        <div className="max-h-[92vh] transition-all duration-200">
            {typeof message.error === "boolean" &&
                message.error !== undefined && (
                    <Toast
                        error={message.error}
                        msg={
                            !message.errors
                                ? message.msg
                                : message.errors.errors[0].code === "blank"
                                  ? "Fields may not be blank."
                                  : message.errors.errors[0].detail
                        }
                    />
                )}
            {loading ? (
                <div className="mt-24">
                    <Skeleton />
                </div>
            ) : (
                <div className="flex w-full">
                    <Sidebar
                        show={showSidebar}
                        station={
                            station &&
                            reStation &&
                            hasDifferences(station, reStation)
                                ? reStation
                                : station
                        }
                        mainParams={locationState?.mainParams ?? undefined}
                        stationMeta={stationMeta}
                        refetchStationMeta={getStationMeta}
                        refetch={refetch}
                        setShow={setShowSidebar}
                    />
                    <Breadcrumb
                        sidebar={showSidebar}
                        state={
                            station &&
                            reStation &&
                            hasDifferences(station, reStation)
                                ? {
                                      ...reStation,
                                      mainParams:
                                          locationState?.mainParams ??
                                          undefined,
                                  }
                                : station
                                  ? {
                                        ...station,
                                        mainParams:
                                            locationState?.mainParams ??
                                            undefined,
                                    }
                                  : locationState
                        }
                    />
                    <div className="w-full flex flex-col pt-20">
                        <div className="flex relative self-center">
                            <h1 className="text-6xl font-bold text-center flex items-center justify-center">
                                {stationTitle}
                            </h1>
                            <div className="absolute -right-[75px] top-3">
                                {location.pathname === `/${nc}/${sc}` && (
                                    <PdfContainer
                                        station={
                                            station &&
                                            reStation &&
                                            hasDifferences(station, reStation)
                                                ? reStation
                                                : station
                                        }
                                        stationMeta={stationMeta}
                                        images={images}
                                        visits={visits}
                                        loadPdf={loadPdf}
                                        stationLocationScreen={
                                            stationLocationScreen
                                        }
                                        stationLocationDetailScreen={
                                            stationLocationDetailScreen
                                        }
                                        loadedMap={loadedMap}
                                        setLoadPdf={setLoadPdf}
                                    />
                                )}

                                {location.pathname === `/${nc}/${sc}/rinex` &&
                                    errorMessages.length > 0 && (
                                        <div className="indicator">
                                            <ExclamationCircleIcon
                                                className={`size-6 fill-red-500`}
                                                title={errorMessages.join("\n")}
                                            />
                                        </div>
                                    )}
                                <button
                                    className={getButtonClasses()}
                                    disabled={reLoading}
                                    onClick={getReStation}
                                    title="Fetch gaps status"
                                >
                                    <ArrowPathIcon className="size-6" />
                                </button>
                            </div>
                        </div>

                        <Outlet
                            context={{
                                station,
                                reStation,
                                stationMeta,
                                showSidebar,
                                images,
                                photoLoading,
                                loadPdf,
                                visitForKml,
                                getStationImages,
                                getReStation,
                                setStationLocationScreen,
                                setStationLocationDetailScreen,
                                setLoadPdf,
                                setLoadedMap,
                            }}
                        />
                    </div>{" "}
                </div>
            )}
        </div>
    );
};

export default Station;
