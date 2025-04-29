import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { MapSkeleton, MapStation, Photo } from "@componentsReact";

import { hasDifferences } from "@utils";

import {
    StationData,
    StationImagesData,
    StationMetadataServiceData,
    StationVisitsData,
} from "@types";

interface OutletContext {
    station: StationData;
    reStation: StationData;
    stationMeta: StationMetadataServiceData;
    images: StationImagesData[];
    visits: StationVisitsData[] | undefined;
    photoLoading: boolean;
    loadPdf: boolean;
    loadedPdfData: boolean;
    loadedMap: boolean;
    getStationImages: () => void;
    setStationLocationScreen: (url: string) => void;
    setStationLocationDetailScreen: (url: string) => void;
    setLoadPdf: React.Dispatch<React.SetStateAction<boolean>>;
    setLoadedMap: React.Dispatch<React.SetStateAction<boolean>>;
}

interface VisitsStates {
    visitId: number;
    checked: boolean;
    color: string;
}

const StationMain = () => {
    const {
        station,
        reStation,
        stationMeta,
        images,
        visits,
        photoLoading,
        loadPdf,
        loadedPdfData,
        getStationImages,
        setStationLocationScreen,
        setStationLocationDetailScreen,
        setLoadPdf,
        setLoadedMap,
    } = useOutletContext<OutletContext>();

    const [changeMeta, setChangeMeta] = useState<boolean>(false);

    const [changeKml, setChangeKml] = useState<VisitsStates[]>([]);

    const [mapFlicker, setMapFlicker] = useState<boolean>(true);

    const definitiveStation =
        station && reStation && hasDifferences(station, reStation)
            ? reStation
            : station;

    const visitsAndMeta = {
        visits: visits ?? [],
        stationMeta: stationMeta,
        changeKml: changeKml,
        changeMeta: changeMeta,
    };

    const visitScrollerProps = {
        visits: visits ?? [],
        changeKml: changeKml,
        changeMeta: changeMeta,
        setChangeKml: setChangeKml,
        setChangeMeta: setChangeMeta,
        stationMeta: stationMeta,
    };

    useEffect(() => {
        setChangeMeta(
            stationMeta &&
                stationMeta.navigation_actual_file !== null &&
                stationMeta.navigation_actual_file !== "",
        );
    }, [stationMeta]);

    useEffect(() => {
        if (visits && stationMeta) {
            setMapFlicker(false);
        }
    }, [visits, stationMeta]);

    return (
        <div>
            <h1 className="text-2xl font-base text-center">
                {station?.country_code?.toUpperCase()}
            </h1>
            <div className="flex flex-col items-center justify-center space-y-4 px-2 pb-4">
                <div className="flex w-full space-x-2 relative">
                    {mapFlicker && (
                        <div className="absolute z-[100] pt-6 ml-2 w-6/12 h-full xl:w-[40vw] lg:w-[30vw] md:w-[30vw] sm:w-[20vw]">
                            <MapSkeleton
                                styles={{
                                    backgroundColor: "rgb(202, 202, 202)",
                                    paddingBottom: "0.7rem",
                                }}
                                height="100%"
                            />
                        </div>
                    )}

                    <MapStation
                        station={definitiveStation}
                        base64Data={
                            changeMeta ||
                            changeKml?.some((visit) => visit.checked)
                                ? (visitsAndMeta ?? "")
                                : ""
                        }
                        loadPdf={loadPdf}
                        loadedPdfData={loadedPdfData}
                        visitScrollerProps={visitScrollerProps}
                        setStationLocationScreen={setStationLocationScreen}
                        setStationLocationDetailScreen={
                            setStationLocationDetailScreen
                        }
                        setLoadPdf={setLoadPdf}
                        setLoadedMap={setLoadedMap}
                    />

                    <Photo
                        loader={photoLoading}
                        phArray={
                            images?.map((img) => {
                                return {
                                    id: img.id ?? 0,
                                    actual_image: img.actual_image ?? "",
                                    description: img.description ?? "",
                                    name: img.name ?? "",
                                };
                            }) ?? []
                        }
                        reFetch={() => {
                            getStationImages();
                        }}
                    />
                </div>
            </div>
        </div>
    );
};

export default StationMain;
