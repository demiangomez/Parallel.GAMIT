import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import {
    CardContainer,
    FormControlSelect,
    Spinner,
    StationSeriesFiltersModal,
} from "@componentsReact";

import { FunnelIcon } from "@heroicons/react/24/outline";

import { getStackNamesService, getStationTimeSeriesService } from "@services";
import { useAuth, useApi } from "@hooks";
import { showModal } from "@utils";

import { SERIES_FILTERS_STATE } from "@utils/reducerFormStates";

import {
    ErrorResponse,
    Errors,
    StationData,
    StationMetadataServiceData,
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
        no_missing_data: false,
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
                | {
                      statusCode: number;
                      time_series: string;
                  }
                | ErrorResponse
            >(api, station.api_id ?? 0, timeSeriesParams);

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
            <h1 className="text-2xl font-base text-center">TIME SERIES</h1>

            <div className="flex flex-grow w-full justify-center pr-2 space-x-2 px-2 pb-4">
                <CardContainer title={""} height={false} addButton={false}>
                    <div className="flex flex-col space-y-2 items-center">
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
                                        no_missing_data: false,
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
                        {timeSeries && (
                            <img
                                src={`data:image/png;base64,${timeSeries}`}
                                alt="Time Series"
                                className="w-[80%] pt-6"
                            />
                        )}
                    </div>
                </CardContainer>

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
                                no_missing_data: false,
                                plot_outliers: false,
                                plot_auto_jumps: false,
                                no_model: false,
                                remove_jumps: false,
                                remove_polynomial: false,
                            });
                        }}
                    />
                )}
            </div>
        </div>
    );
};

export default TimeSeries;
