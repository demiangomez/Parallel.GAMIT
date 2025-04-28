import { useEffect, useMemo, useState } from "react";
import { usePDF } from "@react-pdf/renderer";
import { Pdf } from "@componentsReact";

import { DocumentArrowDownIcon } from "@heroicons/react/24/outline";

import { useApi, useAuth } from "@hooks";

import {
    getMonumentsTypesByIdService,
    getPeopleService,
    getRinexService,
    getRolePersonStationService,
    getStationImagesService,
    getStationInfoService,
    getStationRolesService,
    getStationVisitFilesService,
    getStationVisitGnssFilesService,
    getStationVisitsImagesService,
} from "@services";

import {
    Errors,
    MonumentTypes,
    People,
    RinexData,
    RinexServiceData,
    RolePersonStationData,
    RolePersonStationServiceData,
    StationData,
    StationImagesData,
    StationImagesServiceData,
    StationInfoData,
    StationInfoServiceData,
    StationMetadataServiceData,
    StationStatusServiceData,
    StationVisitsData,
    StationVisitsFilesData,
    StationVisitsFilesServiceData,
} from "@types";

interface Props {
    station: StationData | undefined;
    stationMeta: StationMetadataServiceData | undefined;
    visits: StationVisitsData[] | undefined;
    loadPdf: boolean;
    stationLocationScreen: string;
    stationLocationDetailScreen: string;
    loadedMap: boolean | undefined;
    setMessage: React.Dispatch<
        React.SetStateAction<{
            error: boolean | undefined;
            msg: string;
            errors?: Errors;
        }>
    >;
    setLoadPdf: React.Dispatch<React.SetStateAction<boolean>>;
    setLoadedPdfData: React.Dispatch<React.SetStateAction<boolean | undefined>>;
}

type PeopleWithRole = People & { role: string };

const PdfContainer = ({
    station,
    stationMeta,
    visits,
    loadPdf,
    stationLocationScreen,
    stationLocationDetailScreen,
    loadedMap,
    setMessage,
    setLoadPdf,
    setLoadedPdfData,
}: Props) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [stationInfo, setStationInfo] = useState<StationInfoData | undefined>(
        undefined,
    );

    const [allPeople, setAllPeople] = useState<PeopleWithRole[]>([]);

    const [rolePersonStations, setRolePersonStations] = useState<
        RolePersonStationData[] | undefined
    >(undefined);

    const [roles, setRoles] = useState<any[] | undefined>(undefined);

    const [monuments, setMonuments] = useState<MonumentTypes>();

    const [firstRinex, setFirstRinex] = useState<RinexData | undefined>(
        undefined,
    );
    const [lastRinex, setLastRinex] = useState<RinexData | undefined>(
        undefined,
    );

    const [files, setFiles] = useState<StationVisitsFilesData[] | undefined>(
        undefined,
    );

    const [gnssFiles, setGnssFiles] = useState<
        StationVisitsFilesData[] | undefined
    >(undefined);

    const [images, setImages] = useState<StationImagesData[] | undefined>(
        undefined,
    );

    const [visitImages, setVisitImages] = useState<
        StationVisitsFilesData[] | undefined
    >(undefined);

    const [blobUrl, setBlobUrl] = useState<string | undefined>(undefined);

    const [loading, setLoading] = useState(true);

    const getRinex = async () => {
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
    };

    const getStationPeople = async () => {
        const res =
            await getRolePersonStationService<RolePersonStationServiceData>(
                api,
                {
                    station_api_id: String(station?.api_id),
                    offset: 0,
                    limit: 0,
                },
            );
        setRolePersonStations(res.data);
    };

    const getPeople = async () => {
        const res = await getPeopleService<any>(api);
        setAllPeople(res.data);
    };

    const getRoles = async () => {
        const res = await getStationRolesService<StationStatusServiceData>(api);
        setRoles(res.data);
    };

    const getVisitsGnssFiles = async () => {
        const res =
            await getStationVisitGnssFilesService<StationVisitsFilesServiceData>(
                api,
                {
                    limit: 0,
                    offset: 0,
                    station_api_id: String(station?.api_id),
                    only_metadata: true,
                },
            );
        if (res.statusCode === 200) {
            setGnssFiles(res.data);
        }
    };

    const getVisitsAttachedFiles = async () => {
        const res =
            await getStationVisitFilesService<StationVisitsFilesServiceData>(
                api,
                {
                    limit: 0,
                    offset: 0,
                    station_api_id: String(station?.api_id),
                    only_metadata: true,
                },
            );

        if (res.statusCode === 200) {
            setFiles(res.data);
        }
    };

    const getVisitsImages = async () => {
        const res =
            await getStationVisitsImagesService<StationVisitsFilesServiceData>(
                api,
                {
                    limit: 0,
                    offset: 0,
                    station_api_id: String(station?.api_id),
                    thumbnail: false,
                },
            );

        if (res.statusCode === 200) {
            setVisitImages(res.data);
        }
    };

    const getStationImages = async () => {
        try {
            const result =
                await getStationImagesService<StationImagesServiceData>(api, {
                    offset: 0,
                    limit: 0,
                    station_api_id: String(station?.api_id),
                    thumbnail: true,
                });
            if (result.statusCode === 200) {
                setImages(result.data);
            }
        } catch (err) {
            console.error(err);
        }
    };

    const getMonuments = async () => {
        if (stationMeta?.monument_type === null) return;
        const res = await getMonumentsTypesByIdService<MonumentTypes>(
            api,
            Number(stationMeta?.monument_type),
        );
        setMonuments(res);
    };

    const getLastStationInfo = async () => {
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

            const lastArrayValue = res.data.length - 1;

            setStationInfo(res.data[lastArrayValue]);
        }
    };

    const fetchAllData = async () => {
        setLoading(true);
        try {
            await Promise.all([
                getPeople(),
                getStationPeople(),
                getMonuments(),
                getLastStationInfo(),
                getRoles(),
                getVisitsGnssFiles(),
                getVisitsAttachedFiles(),
                getVisitsImages(),
                getStationImages(),
                getRinex(),
            ]);
        } catch (err) {
            setMessage({ error: true, msg: "Error fetching data" });
            setLoadedPdfData(true);

            // console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const resizeImage = (
        img: HTMLImageElement,
        maxWidth: number,
        maxHeight: number,
    ): Promise<string> => {
        return new Promise((resolve) => {
            const canvas = document.createElement("canvas");
            let width = img.width;
            let height = img.height;

            if (width > maxWidth) {
                height *= maxWidth / width;
                width = maxWidth;
            }
            if (height > maxHeight) {
                width *= maxHeight / height;
                height = maxHeight;
            }

            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext("2d");
            ctx?.drawImage(img, 0, 0, width, height);

            const match = img.src.match(/^data:image\/([a-zA-Z0-9+]+);base64,/);
            const mimeType = match ? `image/${match[1]}` : "image/png";

            resolve(canvas.toDataURL(mimeType, 1));
        });
    };

    const processImages = async (
        images: StationVisitsFilesData[] | StationImagesData[],
    ) => {
        const maxWidth = 800;
        const maxHeight = 800;

        const resizedImagesPromises = images.map(async (img) => {
            const imgElement = new Image();
            const imageExtension = img.name.split(".").pop() || "*";
            imgElement.src = `data:image/${imageExtension};base64,${img.actual_image}`;
            await new Promise((resolve) => {
                imgElement.onload = resolve;
                imgElement.onerror = () => {
                    const isVisitImage = "visit" in img;

                    setMessage({
                        error: true,
                        msg: isVisitImage
                            ? "Error processing visit images/s"
                            : "Error processing station images/s",
                    });
                    setLoadedPdfData(true);
                    // reject(err);
                };
            });

            return await resizeImage(imgElement, maxWidth, maxHeight);
        });

        const resizedImages = await Promise.all(resizedImagesPromises);

        return images.map((img, idx) => ({
            ...img,
            actual_image: resizedImages[idx],
        }));
    };

    const people = useMemo(() => {
        if (rolePersonStations && allPeople) {
            const people = rolePersonStations.map((rps) => {
                const person = allPeople.find((p) => p.id === rps.person);
                if (person) {
                    person.role =
                        roles?.find((r) => r.id === rps.role)?.name ?? "";
                }
                return person;
            });
            return people;
        }
        return [];
    }, [allPeople, rolePersonStations, roles]);

    const [instance, updateInstance] = usePDF({
        document: undefined,
    });

    // SI LOADEDPDFDATA ES TRUE, SE VA EL MODAL DE LOADING.

    useEffect(() => {
        const preparePdfData = async () => {
            try {
                if (
                    (loadPdf && !loadedMap) ||
                    (!loadPdf && !loadedMap) ||
                    loading
                )
                    return;

                let processedImages = visitImages;
                let stationProcessedImages = images;

                if (visitImages && visitImages?.length > 0) {
                    processedImages = (await processImages(
                        visitImages,
                    )) as StationVisitsFilesData[];
                }

                if (images && images?.length > 0) {
                    stationProcessedImages = (await processImages(
                        images,
                    )) as StationImagesData[];
                }

                updateInstance(
                    <Pdf
                        stationInfo={stationInfo}
                        monuments={monuments}
                        station={station}
                        stationMeta={stationMeta}
                        people={people}
                        images={stationProcessedImages}
                        firstRinex={firstRinex}
                        lastRinex={lastRinex}
                        stationLocationScreen={stationLocationScreen}
                        stationLocationDetailScreen={
                            stationLocationDetailScreen
                        }
                        visits={visits}
                        visitFiles={files}
                        visitGnssFiles={gnssFiles}
                        visitImages={processedImages}
                    />,
                );
            } catch (err) {
                console.error(err);
            }
        };

        if (!loadPdf && loadedMap && !loading) {
            preparePdfData(); // Llamar a la función de preparación
        }
    }, [loadPdf, loadedMap, loading, visitImages]);

    useEffect(() => {
        if (!blobUrl && !loadPdf && !loading) {
            if (instance.loading === false && instance.url) {
                setBlobUrl(instance.url);
            }
        }
    }, [instance, blobUrl, loadPdf, loading]);

    useEffect(() => {
        if (blobUrl) {
            const link = document.createElement("a");

            link.href = blobUrl;
            link.download = `${station?.network_code?.toUpperCase() ?? "none"}.${station?.station_code?.toUpperCase() ?? "none"}-INFO.pdf`;
            link.click();
            setLoadedPdfData(true);
        }
    }, [blobUrl]);

    return (
        <button
            className={`hover:scale-110 btn-ghost rounded-lg p-1 transition-all align-top`}
            title="Download station pdf"
            onClick={() => {
                fetchAllData();
                setMessage({ error: undefined, msg: "" });
                setBlobUrl(undefined);
                setLoadedPdfData(false);
                setLoadPdf(true);
            }}
        >
            <DocumentArrowDownIcon className="size-6" />
        </button>
    );
};

export default PdfContainer;
