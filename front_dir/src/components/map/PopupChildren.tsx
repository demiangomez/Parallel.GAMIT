import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";

import useApi from "@hooks/useApi";
import { useAuth } from "@hooks/useAuth";
import { getRinexService, getStationMetaService} from "@services";

import {
    GetParams,
    RinexData,
    RinexServiceData,
    StationData,
    StationMetadataServiceData,
} from "@types";

import { formattedDates, generateErrorMessages, woTz } from "@utils";

interface PopupChildrenProps {
    station: StationData | undefined;
    fromMain?: boolean | undefined;
    mainParams?: GetParams;
}

const child = (key: string, text: string, idx: number) => {
    return (
        <div key={idx} className="flex flex-col w-full">
            <span className="text-sm">
                <strong>{key}:</strong> {text}
            </span>
        </div>
    );
};

const PopupChildren = ({
    station,
    fromMain,
    mainParams,
}: PopupChildrenProps) => {
    const { station_code, network_code, country_code, lat, lon, height } =
        station || {};

    const outletContext = useOutletContext<{
        stationMeta: StationMetadataServiceData;
    }>();
    const stationMeta = outletContext ? outletContext.stationMeta : undefined;

    const data = {
        Station: station_code,
        Network: network_code,
        Country: country_code,
        Latitude: lat?.toFixed(8),
        Longitude: lon?.toFixed(8),
        Height: height?.toFixed(3),
    };


    
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [firstRinex, setFirstRinex] = useState<RinexData | undefined>(
        undefined,
    );
    const [lastRinex, setLastRinex] = useState<RinexData | undefined>(
        undefined,
    );

    const [stationMetaByMain, setStationMetaByMain] = useState<
        StationMetadataServiceData | undefined
    >(undefined);

    const [loading, setLoading] = useState(false);

    const getRinex = async () => {
        try {
            setLoading(true);
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
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const getStationMeta = async () => {
        try {
            const res = await getStationMetaService<StationMetadataServiceData>(
                api,
                Number(station?.api_id),
            );
            if (res) {
                setStationMetaByMain(res);
            }
        } catch (err) {
            console.error(err);
        }
    };

    const getDistinctVisitYears = (key: string) => {
        if(stationMetaByMain?.[key as keyof StationMetadataServiceData] && (stationMetaByMain?.[key as keyof StationMetadataServiceData] as string[]).join(", ") !== ""){
            const valores = stationMetaByMain?.[key as keyof StationMetadataServiceData] as string[];
            valores.sort((a, b) => Number(a) - Number(b));
            return valores.join(", ");
        }
        else{
            return "-";
        }

    };

    const errorMessages = station ? generateErrorMessages(station) : [];

    useEffect(() => {
        if (fromMain) {
            getRinex();
            getStationMeta();
        }
    }, [fromMain]);

    

    const campsToShow = ["rinex_count", "distinct_visit_years", "station_name"];

    return (
        <div
            className={`flex flex-col self-start space-y-2 max-h-82 overflow-y-auto pr-2 md:w-[400px] lg:w-[450px] `}
        >
            <span className="w-full bg-green-400 px-4 py-1 text-center font-bold self-center">
                {fromMain
                    ? stationMetaByMain?.station_type_name
                        ? stationMetaByMain?.station_type_name.toUpperCase()
                        : "Station type not defined"
                    : stationMeta?.station_type_name
                      ? stationMeta?.station_type_name.toUpperCase()
                      : "Station type not defined"}
            </span>
            <div className="flex justify-between w-full divide-x-2">
                <div className="flex flex-col grow justify-center space-y-2">
                    {Object.entries(data).map((d, idx) =>
                        child(String(d[0]), String(d[1]), idx),
                    )}
                    {
                        fromMain? campsToShow.map((key, idx) => {
                            if(key !== "distinct_visit_years") {
                                return (
                                    <div key = {idx} className="flex flex-col w-full">
                                        <span className="text-sm">
                                            <strong>{key.replace(/_/g, " ").replace(/^\w/, c => c.toUpperCase())}:</strong>{" "}
                                            {stationMetaByMain?.[key as keyof StationMetadataServiceData] ? stationMetaByMain[key as keyof StationMetadataServiceData] : "-"}
                                        </span>
                                    </div>
                                );
                            }
                            else{
                                return (
                                    <div key = {idx} className="flex flex-col w-full">
                                        <span className="text-sm flex flex-row flex-wrap">
                                            <strong>{key.replace(/_/g, " ").replace(/^\w/, c => c.toUpperCase())}: </strong>
                                                <div className={Array.isArray(stationMetaByMain?.[key as keyof StationMetadataServiceData]) && (stationMetaByMain?.[key as keyof StationMetadataServiceData] as string[]).length > 1 ? "" : "ml-1"}>
                                                {getDistinctVisitYears(key)}
                                                </div>
                                        </span>
                                    </div>
                                );
                            }
                            }) : !fromMain && stationMeta ? campsToShow.map((key, idx) => {
                                if(key !== "distinct_visit_years") {
                                    return (
                                        <div key = {idx} className="flex flex-col w-full">
                                            <span className="text-sm">
                                                <strong>{key.replace(/_/g, " ").replace(/^\w/, c => c.toUpperCase())}:</strong>{" "}
                                                {stationMeta?.[key as keyof StationMetadataServiceData] ?  stationMeta[key as keyof StationMetadataServiceData]  : "-"} 
                                            </span>
                                        </div>
                                    );
                                }
                                else{
                                    return (
                                        <div key = {idx} className="flex flex-col w-full">
                                            <span className="text-sm flex flex-row flex-wrap">
                                                <strong className="pr-1">{key.replace(/_/g, " ").replace(/^\w/, c => c.toUpperCase())}:</strong>{" "}
                                                {
                                                    stationMeta?.[key as keyof StationMetadataServiceData] ?  
                                                    (stationMeta?.[key as keyof StationMetadataServiceData] as string[]).join(", ")  : "-"
                                                }
                                            </span>
                                        </div>
                                    );
                                }
                        })
                        :null
                    }
                </div>
                {fromMain && loading ? (
                    <span className="loading loading-dots loading-lg mx-auto"></span>
                ) : fromMain !== undefined && !loading ? (
                    <div className="flex text-sm flex-col gap-4 justify-center items-start grow pl-4 mb-4">
                        {firstRinex ? (
                            <div className="flex flex-col justify-center items-start">
                                <h2 className="text-md font-semibold pt-2 text-gray-500">
                                    First Rinex
                                </h2>
                                <div className="flex">
                                    <strong>Filename: </strong>
                                    <span
                                        className="ml-1"
                                        title={firstRinex.filename}
                                    >
                                        {firstRinex.filename.length > 15
                                            ? firstRinex.filename.slice(0, 15) +
                                              "..."
                                            : firstRinex.filename}
                                    </span>
                                </div>
                                <div className="flex flex-row">
                                    <strong>Obs day: </strong>
                                    <span className="ml-1">
                                        {" "}
                                        {formattedDates(
                                            new Date(
                                                firstRinex.observation_s_time,
                                            ),
                                        )}
                                    </span>
                                </div>
                            </div>
                        ) : (
                            <strong className="my-auto">
                                No Rinex for this station
                            </strong>
                        )}
                        {lastRinex && (
                            <div className="flex flex-col">
                                <h2 className="text-md font-semibold pt-2 text-gray-500">Last Rinex</h2>
                                <div className="flex">
                                    <strong>Filename: </strong>
                                    <span
                                        className="ml-1"
                                        title={lastRinex.filename}
                                    >
                                        {lastRinex.filename.length > 15
                                            ? lastRinex.filename.slice(0, 15) +
                                              "..."
                                            : lastRinex.filename}
                                    </span>
                                </div>
                                <div className="flex">
                                    <strong>Obs day: </strong>
                                    <span className="ml-1">
                                        {formattedDates(
                                            new Date(
                                                lastRinex.observation_s_time,
                                            ),
                                        )}
                                    </span>
                                </div>
                            </div>
                        )}
                    </div>
                ) : null}
            </div>

            {
                <div className="w-full flex flex-col border-t-2 pt-2">
                    {!fromMain && (
                        <div className="flex flex-col items-center text-sm my-2">
                            <span className="font-bold">Last gaps update </span>
                            <span>
                                {stationMeta?.has_gaps_last_update_datetime
                                    ? (formattedDates(
                                          woTz(
                                              new Date(
                                                  stationMeta.has_gaps_last_update_datetime as string,
                                              ),
                                          ) as Date,
                                      ) ?? "")
                                    : "No update date available"}
                            </span>
                        </div>
                    )}
                    <span className="text-base text-error border-b-2">
                        Station errors
                    </span>
                    {station &&
                    ((station.gaps && station.gaps.length > 0) ||
                        !station?.has_stationinfo) ? (
                        <div className="flex flex-col">
                            {errorMessages.length > 0 && (
                                <div className="flex flex-col my-2 space-y-2">
                                    {errorMessages.map((message, idx) => (
                                        <div key={idx} className="flex">
                                            <span className="text-sm text-red-500">
                                                {message}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="flex flex-col my-2">
                            <span className="text-sm">No errors</span>
                        </div>
                    )}
                </div>
            }

            {fromMain && (
                <Link
                    to={`/${network_code}/${station_code}`}
                    className=" text-center"
                    state={{ ...station, mainParams: mainParams }}
                >
                    {" "}
                    Navigate to Station{" "}
                </Link>
            )}
        </div>
    );
};
export default PopupChildren;
