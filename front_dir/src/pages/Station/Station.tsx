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
    getKmzFileService,
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
    KmzFile,
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
    const [loadedPdfData, setLoadedPdfData] = useState<boolean | undefined>(
        undefined,
    );

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
        } finally {
            setLoading(false);
        }
    };

    const getReStation = async () => {
        try {
            getStationMeta();
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
                Number(station?.api_id ?? locationState.api_id),
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
                    station_api_id: String(
                        station?.api_id ?? locationState.api_id,
                    ),
                    thumbnail: true,
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
                    station_api_id: String(
                        station?.api_id ?? locationState.api_id,
                    ),
                },
            );

            if (res.statusCode === 200) {
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

    const isMainLocation =
        location.pathname === `/${nc}/${sc}` ||
        location.pathname === `/${nc}/${sc}/`;

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
        if (locationState && !loading && !station) {
            setStation(locationState);
        } else if (!station) {
            getStation();
        }
    }, [locationState, station]); //eslint-disable-line

    useEffect(() => {
        if (station) {
            if (isMainLocation) {
                getStationImages();
                getVisits();
            }
            getStationMeta();
        }
    }, [station, locationState]); //eslint-disable-line

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
            // if (location.pathname === `/${nc}/${sc}`) {
            //     getVisits();
            // }
            setLoadPdf(false);
            setLoadedPdfData(undefined);
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

    const [kmzFile, setKmzFile] = useState<string | undefined>(undefined);

    const getKmzBalloon = async () => {
        try {
            if(station?.api_id){
                const res = await getKmzFileService<KmzFile>(api, station?.api_id.toString());
                if(res.statusCode == 200){
                    setKmzFile(res.kmz)
                }
            } 
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        if (kmzFile !== undefined && kmzFile !== "") {
            const byteCharacters = atob(kmzFile); 
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
    
            const blob = new Blob([byteArray], { type: 'application/octet-stream' });
    
            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.download = `${station?.network_code}_${station?.station_code}.kmz`; 
    
            document.body.appendChild(link);
            link.click();
    
            document.body.removeChild(link);
            URL.revokeObjectURL(link.href); 
        }
    }, [kmzFile]);

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
                        <div className="flex relative self-center gap-2">
                            <h1 className="text-6xl font-bold text-center flex items-center justify-center">
                                {stationTitle}
                            </h1>
                                <div className="flex items-center justify-start min-w-[100px] gap-0 absolute -right-[105px] top-3">
                                    {location.pathname === `/${nc}/${sc}` && (
                                        <>
                                        <PdfContainer
                                            station={
                                                station &&
                                                reStation &&
                                                hasDifferences(station, reStation)
                                                    ? reStation
                                                    : station
                                            }
                                            stationMeta={stationMeta}
                                            visits={visits}
                                            loadPdf={loadPdf}
                                            stationLocationScreen={
                                                stationLocationScreen
                                            }
                                            stationLocationDetailScreen={
                                                stationLocationDetailScreen
                                            }
                                            loadedMap={loadedMap}
                                            // loadPdfdata={loadPdfData}
                                            setMessage={setMessage}
                                            setLoadPdf={setLoadPdf}
                                            setLoadedPdfData={setLoadedPdfData}
                                        />
                                        
                                        <a href="#" className={"flex items-center justify-center " + getButtonClasses()} title="Download station kmz" 
                                        onClick={(e) => {e.preventDefault(); getKmzBalloon();}}
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-6">
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M12.75 3.03v.568c0 .334.148.65.405.864l1.068.89c.442.369.535 1.01.216 1.49l-.51.766a2.25 2.25 0 0 1-1.161.886l-.143.048a1.107 1.107 0 0 0-.57 1.664c.369.555.169 1.307-.427 1.605L9 13.125l.423 1.059a.956.956 0 0 1-1.652.928l-.679-.906a1.125 1.125 0 0 0-1.906.172L4.5 15.75l-.612.153M12.75 3.031a9 9 0 0 0-8.862 12.872M12.75 3.031a9 9 0 0 1 6.69 14.036m0 0-.177-.529A2.25 2.25 0 0 0 17.128 15H16.5l-.324-.324a1.453 1.453 0 0 0-2.328.377l-.036.073a1.586 1.586 0 0 1-.982.816l-.99.282c-.55.157-.894.702-.8 1.267l.073.438c.08.474.49.821.97.821.846 0 1.598.542 1.865 1.345l.215.643m5.276-3.67a9.012 9.012 0 0 1-5.276 3.67m0 0a9 9 0 0 1-10.275-4.835M15.75 9c0 .896-.393 1.7-1.016 2.25" />
                                            </svg>

                                        </a>
                                        </>)
                                    }

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
                                loadedMap,
                                loadedPdfData,
                                visits,
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
