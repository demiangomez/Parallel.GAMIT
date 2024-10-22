import {
    NavigationType,
    Outlet,
    useLocation,
    useNavigate,
    useParams,
} from "react-router-dom";
import { router } from "App";

import { useEffect, useState } from "react";

import { Sidebar, Skeleton, Breadcrumb, PdfContainer } from "@componentsReact";

import { useAuth } from "@hooks/useAuth";

import useApi from "@hooks/useApi";

import {
    getStationImagesService,
    getStationMetaService,
    getStationsService,
    getStationVisitsService,
} from "@services";

import {
    StationData,
    StationImagesData,
    StationImagesServiceData,
    StationMetadataServiceData,
    StationServiceData,
    StationVisitsData,
    StationVisitsServiceData,
} from "@types";
import { generateErrorMessages } from "@utils/index";
import { ExclamationCircleIcon } from "@heroicons/react/24/outline";

const Station = () => {
    const { sc, nc } = useParams<{ sc: string; nc: string }>();
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [station, setStation] = useState<StationData | undefined>(undefined);

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

    const location = useLocation();

    const [showSidebar, setShowSidebar] = useState<boolean>(false);

    const locationState = location.state as StationData;

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
                            navigate("/", { state: locationState });
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

    const errorMessages = station ? generateErrorMessages(station) : [];

    return (
        <div className="max-h-[92vh] transition-all duration-200">
            {loading ? (
                <div className="mt-24">
                    <Skeleton />
                </div>
            ) : (
                <div className="flex w-full">
                    <Sidebar
                        show={showSidebar}
                        station={station}
                        stationMeta={stationMeta}
                        refetchStationMeta={getStationMeta}
                        refetch={refetch}
                        setShow={setShowSidebar}
                    />
                    <Breadcrumb
                        sidebar={showSidebar}
                        state={station ? station : locationState}
                    />
                    <div className="w-full flex flex-col pt-20">
                        <h1 className="text-6xl font-bold text-center flex items-center justify-center">
                            {stationTitle}

                            {location.pathname === `/${nc}/${sc}` && (
                                <PdfContainer
                                    station={station}
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
                                    <div className="indicator absolute bottom-2 left-2">
                                        <ExclamationCircleIcon
                                            className={`size-7 fill-red-500`}
                                            title={errorMessages.join("\n")}
                                        />
                                    </div>
                                )}
                        </h1>
                        <Outlet
                            context={{
                                station,
                                stationMeta,
                                showSidebar,
                                images,
                                photoLoading,
                                loadPdf,
                                visitForKml,
                                getStationImages,
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
