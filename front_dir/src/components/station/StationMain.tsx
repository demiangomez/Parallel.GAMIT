import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { MapStation, Photo } from "@componentsReact";

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
    visitForKml: StationVisitsData;
    photoLoading: boolean;
    loadPdf: boolean;
    loadedMap: boolean;
    getStationImages: () => void;
    setStationLocationScreen: (url: string) => void;
    setStationLocationDetailScreen: (url: string) => void;
    setLoadPdf: React.Dispatch<React.SetStateAction<boolean>>;
    setLoadedMap: React.Dispatch<React.SetStateAction<boolean>>;
}

const StationMain = () => {
    const {
        station,
        reStation,
        stationMeta,
        images,
        visitForKml,
        photoLoading,
        loadPdf,
        getStationImages,
        setStationLocationScreen,
        setStationLocationDetailScreen,
        setLoadPdf,
        setLoadedMap,
    } = useOutletContext<OutletContext>();

    const [changeKml, setChangeKml] = useState<boolean | undefined>(undefined);

    return (
        <div>
            <h1 className="text-2xl font-base text-center">
                {station?.country_code?.toUpperCase()}
            </h1>
            {visitForKml && visitForKml.navigation_actual_file ? (
                <div className="w-fit ml-2 bg-base-200 rounded-md">
                    <div className=" pt-2 flex p-2 items-center justify-start z-20">
                        <div className="form-control">
                            <label className="label cursor-pointer">
                                <span className="font-bold mr-4">
                                    Last visit navigation file
                                </span>
                                <input
                                    type="checkbox"
                                    className="checkbox checkbox-sm"
                                    onChange={() => setChangeKml(!changeKml)}
                                />
                            </label>
                        </div>
                    </div>
                </div>
            ) : null}
            <div className="flex w-full pr-2 space-x-2 px-2">
                <MapStation
                    station={
                        station &&
                        reStation &&
                        hasDifferences(station, reStation)
                            ? reStation
                            : station
                    }
                    base64Data={
                        changeKml
                            ? visitForKml.navigation_actual_file ?? ""
                            : stationMeta?.navigation_actual_file ?? ""
                    }
                    loadPdf={loadPdf}
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
    );
};

export default StationMain;
