import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import {
    CardContainer,
    FormControlSelect,
    Spinner,
    StationSeriesFiltersModal,
    StationTimeSeriesDetailModal,
    TimeSeriesParams,
} from "@componentsReact";

import { FunnelIcon, DocumentChartBarIcon, BookmarkIcon } from "@heroicons/react/24/outline";

import { getStackNamesService, getStationTimeSeriesService } from "@services";
import { useAuth, useApi } from "@hooks";
import { showModal } from "@utils";

import { SERIES_FILTERS_STATE } from "@utils/reducerFormStates";

import {
    ErrorResponse,
    Errors,
    StationData,
    StationMetadataServiceData,
    TimeSeriesParamsData,
    ConfigPolynomialData,
    ConfigJumpData
} from "@types";

interface OutletContext {
    station: StationData;
    reStation: StationData;
    stationMeta: StationMetadataServiceData;
}

const TimeSeries = () => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const { station } = useOutletContext<OutletContext>();


    const [loading, setLoading] = useState<boolean>(false);

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [loadingJson, setLoadingJson] = useState<boolean>(false);

    const [polynomialData, setPolynomialData] = useState<ConfigPolynomialData | undefined>(undefined);
    const [periodicData, setPeriodicData] = useState<any | undefined>(undefined);
    const [jumpsData, setJumpsData] = useState<ConfigJumpData[] | undefined>(undefined);
    const [solutions] = useState<string[]>(["PPP", "GAMIT"]);
    const [solutionSelected, setSolutionSelected] = useState<string>("PPP");
    const [stackSelected, setStackSelected] = useState<string>("");

    const [stacks, setStacks] = useState<string[] | undefined>(undefined);

    const [timeSeries, setTimeSeries] = useState<string | undefined>(undefined);

    const [params, setParams] = useState<
        Record<keyof typeof SERIES_FILTERS_STATE, string | boolean>
    >({
        solution: solutionSelected,
        stack: stackSelected,
        date_start: "",
        date_end: "",
        residuals: false,
        missing_data: false,
        plot_outliers: false,
        plot_auto_jumps: false,
        no_model: false,
        remove_jumps: false,
        remove_polynomial: false,
    });

    const getStacksNames = async () => {
        try {
            const res = await getStackNamesService<{
                stack_names: string[];
                statusCode: number;
            }>(api, station.api_id ?? 0);

            setStacks(res.stack_names);
        } catch (e) {
            console.error(e);
            setMsg({ status: 500, msg: "Error fetching stack names" });
        }
    };

    const getJsonFile = async () => {
        getJsonTimeSeries();
    }

    const getJsonTimeSeries = async () => {
        try {
            setLoadingJson(true);
            const timeSeriesParams = {
                ...params,
            };

            for (const key in timeSeriesParams) {
                if (
                    timeSeriesParams[key as keyof typeof timeSeriesParams] ===
                    ""
                ) {
                    delete timeSeriesParams[
                        key as keyof typeof timeSeriesParams
                    ];
                }

                if (
                    key.includes("date") &&
                    timeSeriesParams[key as keyof typeof timeSeriesParams]
                ) {
                    timeSeriesParams[key as keyof typeof timeSeriesParams] = (
                        timeSeriesParams[
                            key as keyof typeof timeSeriesParams
                        ] as string
                    )?.replace(/-/g, "/");
                }
            }

            const res = await getStationTimeSeriesService<
            | 
                {
                    etm_params: TimeSeriesParamsData;
                    time_series: string;
                }
            | ErrorResponse
            >(api, station.api_id ?? 0, timeSeriesParams, true);

            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.errors[0].detail,
                    errors: res.response,
                });
            } else {
                setMsg(undefined);
                const jsonData = JSON.stringify(res.time_series, null, 2);
                const blob = new Blob([jsonData], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = 'timeseries.json';
                link.click();
                URL.revokeObjectURL(url);
            }
        } catch (e) {
            console.error(e);
            setMsg({ status: 500, msg: "Error fetching time series" });
        }finally{
            setLoadingJson(false);
        }
    }

    const handleShowReference = () => {
        setModals({
            show: true,
            title: "station-time-series-detail-modal",
            type: "none",
        });
    }

    const getTimeSeries = async () => {
        setLoading(true);
        setMsg(undefined);
        setTimeSeries(undefined);
        try {
            const timeSeriesParams = {
                ...params,
            };

            for (const key in timeSeriesParams) {
                if (
                    timeSeriesParams[key as keyof typeof timeSeriesParams] ===
                    ""
                ) {
                    delete timeSeriesParams[
                        key as keyof typeof timeSeriesParams
                    ];
                }

                if (
                    key.includes("date") &&
                    timeSeriesParams[key as keyof typeof timeSeriesParams]
                ) {
                    timeSeriesParams[key as keyof typeof timeSeriesParams] = (
                        timeSeriesParams[
                            key as keyof typeof timeSeriesParams
                        ] as string
                    )?.replace(/-/g, "/");
                }
            }

            const res = await getStationTimeSeriesService<
            | 
                {
                    etm_params: TimeSeriesParamsData;
                    time_series: string;
                }
            | ErrorResponse
            >(api, station.api_id ?? 0, timeSeriesParams, false);

            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.errors[0].detail,
                    errors: res.response,
                });
            } else {
                setMsg(undefined);
                setTimeSeries(res.time_series);
            }
            if(res && !("status" in res) && res.etm_params){
                if(res.etm_params.polynomial){
                    setPolynomialData(res.etm_params.polynomial);
                }
                if(res.etm_params.jumps){
                    setJumpsData(res.etm_params.jumps);
                }
                if(res.etm_params.periodic){
                    setPeriodicData(res.etm_params.periodic);
                }
            }
        } catch (e) {
            console.error(e);
            setMsg({ status: 500, msg: "Error fetching time series" });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (solutionSelected === "PPP") {
            setStackSelected("");
        } else if (stacks && stacks.length > 0) {
            setStackSelected(stacks[0]);
        }
    }, [stacks, solutionSelected]);

    useEffect(() => {
        setParams((prev) => ({
            ...prev,
            stack: stackSelected,
            solution: solutionSelected,
        }));
    }, [stackSelected, solutionSelected]);

    useEffect(() => {
        getStacksNames();
    }, []);

    useEffect(() => {
        if (
            (params.stack && solutionSelected !== "PPP") ||
            (!params.stack && solutionSelected === "PPP")
        ) {
            getTimeSeries();
        }
    }, [params.stack]);

    useEffect(() => {
        if (modals?.show) {
            showModal(modals.title);
        }
    }, [modals]);

    return (
        <div className="">
            <h1 className="text-2xl font-base text-center">{station ? "TIME SERIES": "TIME SERIES NOT FOUND"}</h1>
            { station  &&
            <div className="flex flex-grow w-full justify-center pr-2 space-x-2 px-2 pb-4">
                {
                <CardContainer title={""} height={false} addButton={false} >
                    <div className="flex flex-col space-y-4 items-center w-[100%]">
                        <div className="flex flex-col space-y-2 items-center w-full">
                            <div className="w-full flex flex-row">
                                <BookmarkIcon className="size-6 cursor-pointer"
                                    onClick={handleShowReference}
                                />
                                <div className="w-full flex space-x-4 justify-center">
                                    <FormControlSelect
                                        title={"Solution"}
                                        options={solutions}
                                        optionSelected={solutionSelected}
                                        optionDisabled={
                                            stacks?.length === 0 ? "GAMIT" : ""
                                        }
                                        selectFunction={(option: string) => {
                                            setSolutionSelected(option);
                                            setParams({
                                                solution: solutionSelected,
                                                stack: stackSelected,
                                                date_start: "",
                                                date_end: "",
                                                residuals: false,
                                                missing_data: false,
                                                plot_outliers: false,
                                                plot_auto_jumps: false,
                                                no_model: false,
                                                remove_jumps: false,
                                                remove_polynomial: false,
                                            });
                                        }}
                                    />
                                    {solutionSelected === "GAMIT" &&
                                        stacks &&
                                        stacks.length > 0 && (
                                            <FormControlSelect
                                                title={"Stack"}
                                                options={stacks ?? []}
                                                optionSelected={stackSelected}
                                                selectFunction={(option: string) => {
                                                    setStackSelected(option);
                                                }}
                                            />
                                        )}

                                    <button
                                        className="btn self-end"
                                        onClick={() =>
                                            setModals({
                                                show: true,
                                                title: "SeriesFilters",
                                                type: "none",
                                            })
                                        }
                                    >
                                        Parameters
                                        <FunnelIcon className="size-6" />
                                        
                                    </button>
                                    <button
                                        className="btn self-end"
                                        onClick={() =>
                                            getJsonFile()
                                        }
                                    >
                                        Json
                                        { loadingJson ?
                                            <Spinner size="md" />
                                            :<DocumentChartBarIcon className="size-6" />
                                        }

                                        
                                    </button>
                                </div>
                            </div>
                            {loading && (
                                <div className="py-24">
                                    <Spinner size="lg" />
                                </div>
                            )}
                            {msg && (
                                <div className="font-bold text-xl p-4 flex relative items-center justify-center h-32">
                                    <span className="text-gray-300 text-base absolute right-3 self-end">
                                        {msg.errors?.errors[0].code.toUpperCase()}
                                    </span>
                                    <span className="text-neutral text-2xl">
                                        {msg.msg.toUpperCase()}
                                    </span>
                                </div>
                            )}
                            {timeSeries && !loading &&(
                                <img
                                    src={`data:image/png;base64,${timeSeries}`}
                                    alt="Time Series"
                                    className="w-[95%] pt-6"
                                />
                            )}
                        </div>
                        { !loading &&
                        <div className="w-[95%]">
                            <TimeSeriesParams
                                stationId={station.api_id? station.api_id : 0}
                                refetch = {getTimeSeries}
                                solution = {solutionSelected}
                                jumpsData = {jumpsData}
                                periodicData = {periodicData}
                                polynomialData = {polynomialData}
                                stack = {stackSelected}
                            />
                        </div>
                        }
                    </div>
                </CardContainer>
                }

                {modals?.show && modals?.title === "SeriesFilters" && (
                    <StationSeriesFiltersModal
                        filters={params}
                        setFilters={setParams}
                        setStateModal={setModals}
                        handleSubmit={() => {
                            getTimeSeries();
                            setModals(undefined);
                        }}
                        handleCleanFilters={() => {
                            setParams({
                                solution: solutionSelected,
                                stack: stackSelected,
                                date_start: "",
                                date_end: "",
                                residuals: false,
                                missing_data: false,
                                plot_outliers: false,
                                plot_auto_jumps: false,
                                no_model: false,
                                remove_jumps: false,
                                remove_polynomial: false,
                            });
                        }}
                    />
                )}
                { modals?.show && modals?.title === "station-time-series-detail-modal" &&
                    <StationTimeSeriesDetailModal/>
                }
            </div>
        }
        </div>
    );
};

export default TimeSeries;
