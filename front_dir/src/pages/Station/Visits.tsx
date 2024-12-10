import { useLocation, useOutletContext } from "react-router-dom";
import { useEffect, useState } from "react";
import {
    CardContainer,
    ConfirmDeleteModal,
    MapVisit,
    Spinner,
    TableCard,
    TableSkeleton,
    VisitAddModal,
    VisitDetailModal,
} from "@componentsReact";

import useApi from "@hooks/useApi";
import { useAuth } from "@hooks/useAuth";

import {
    delStationVisitService,
    getStationCampaignsService,
    getStationVisitsImagesService,
    getStationVisitsService,
} from "@services";

import {
    ErrorResponse,
    Errors,
    StationCampaignsData,
    StationCampaignsServiceData,
    StationData,
    StationVisitsData,
    StationVisitsFilesData,
    StationVisitsFilesServiceData,
    StationVisitsServiceData,
} from "@types";

import { Bars3BottomRightIcon, TrashIcon } from "@heroicons/react/24/outline";

import { showModal } from "@utils";

interface OutletContext {
    station: StationData;
}

const Visits = () => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const location = useLocation();

    const campaign = location.state
        ? "visitDetail" in location.state
            ? undefined
            : "start_date" in location.state
              ? (location.state as StationCampaignsData)
              : undefined
        : undefined;

    const visitByCampaign = location.state
        ? "visitDetail" in location.state
            ? (location.state.visitDetail as StationVisitsData)
            : undefined
        : undefined;

    const { station } = useOutletContext<OutletContext>();

    const [loading, setLoading] = useState<boolean>(false);
    const [loadingVisitImages, setLoadingVisitImages] =
        useState<boolean>(false);

    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const [visits, setVisits] = useState<StationVisitsData[] | undefined>(
        undefined,
    );

    const [visitToDel, setVisitToDel] = useState<number | undefined>(undefined);

    const [campaigns, setCampaigns] = useState<
        StationCampaignsData[] | undefined
    >(undefined);

    const [images, setImages] = useState<StationVisitsFilesData[] | undefined>(
        undefined,
    );

    const [visit, setVisit] = useState<StationVisitsData | undefined>(
        undefined,
    );

    const getVisits = async () => {
        try {
            setLoading(true);
            const res = await getStationVisitsService<StationVisitsServiceData>(
                api,
                {
                    limit: 0,
                    offset: 0,
                    station_api_id: String(station?.api_id),
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

    const getCampaigns = async () => {
        try {
            setLoading(true);
            const res =
                await getStationCampaignsService<StationCampaignsServiceData>(
                    api,
                    {
                        limit: 0,
                        offset: 0,
                    },
                );

            if (res.statusCode === 200) {
                setCampaigns(res.data);
            }
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const getVisitsImages = async () => {
        try {
            setLoadingVisitImages(true);
            const res =
                await getStationVisitsImagesService<StationVisitsFilesServiceData>(
                    api,
                    {
                        limit: 0,
                        offset: 0,
                        station_api_id: String(station?.api_id),
                        thumbnail: true,
                    },
                );

            if (res.statusCode === 200) {
                setImages(res.data);
            }
        } catch (error) {
            console.error(error);
        } finally {
            setLoadingVisitImages(false);
        }
    };

    const delVisit = async () => {
        try {
            setLoading(true);

            const res = await delStationVisitService<ErrorResponse>(
                api,
                visitToDel ?? 0,
            );

            if ("status" in res && res.status === "success") {
                setMsg({
                    status: res.statusCode,
                    msg: res.msg,
                });
            } else {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (station && station.api_id) {
            getVisits();
            getVisitsImages();
            getCampaigns();
        }
    }, [station]); // eslint-disable-line

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    useEffect(() => {
        if (campaign && !visitByCampaign) {
            setModals({
                show: true,
                title: "AddVisit",
                type: "edit",
            });
        } else if (!campaign && visitByCampaign) {
            setModals({
                show: true,
                title: "VisitDetail",
                type: "none",
            });
            delete visitByCampaign?.station_formatted;
            setVisit(visitByCampaign);
        }
    }, [campaign, visitByCampaign]);

    return (
        <div className="">
            <h1 className="text-2xl font-base text-center">VISITS</h1>

            <div className="flex flex-grow w-full justify-center pr-2 space-x-2 px-2 pb-4">
                <CardContainer title="" titlePosition="start">
                    <TableCard
                        title={"Visits"}
                        size={"100%"}
                        addButtonTitle="Add Visit"
                        modalTitle="AddVisit"
                        setModals={setModals}
                        addButton={true}
                    >
                        {loading ? (
                            <div className="grid gap-4 grid-cols-3 grid-flow-dense">
                                {Array.from({ length: 3 }).map((_, i) => (
                                    <TableSkeleton mainSize="300px" key={i} />
                                ))}
                            </div>
                        ) : visits && visits.length === 0 ? (
                            <div className="text-center text-neutral text-2xl font-bold w-full rounded-md bg-neutral-content p-6">
                                There is no visits
                            </div>
                        ) : (
                            <div
                                className={`grid 
                                    ${visits && visits.length === 1 ? "grid-cols-1" : visits && visits.length > 2 && "grid-cols-2"} 
                                grid-flow-dense gap-4`}
                            >
                                {visits?.map((vis) => {
                                    const visitImages = images?.filter(
                                        (i) => i.visit === vis.id,
                                    );

                                    return (
                                        <div
                                            key={vis.id}
                                            className="card bg-neutral-content"
                                        >
                                            <div className="inline-flex self-end">
                                                <button
                                                    title={"delete"}
                                                    className="btn btn-ghost btn-circle"
                                                    onClick={() => {
                                                        setModals({
                                                            show: true,
                                                            title: "ConfirmDelete",
                                                            type: "edit",
                                                        });
                                                        setVisitToDel(vis.id);
                                                    }}
                                                >
                                                    <TrashIcon className="size-8 text-red-600" />
                                                </button>
                                                <button
                                                    title={"details"}
                                                    className="btn btn-ghost btn-circle"
                                                    onClick={() => {
                                                        setModals({
                                                            show: true,
                                                            title: "VisitDetail",
                                                            type: "none",
                                                        });
                                                        setVisit(vis);
                                                    }}
                                                >
                                                    <Bars3BottomRightIcon className="size-8" />
                                                </button>
                                            </div>
                                            <div className="card-body space-y-4">
                                                <h2 className="text-2xl self-center">
                                                    <span className="font-semibold ">
                                                        Visit date{" "}
                                                    </span>
                                                    {vis?.date}
                                                </h2>
                                                <span className="self-center text-xl">
                                                    <span className="font-semibold ">
                                                        Campaign{" "}
                                                    </span>
                                                    {vis?.campaign
                                                        ? campaigns?.find(
                                                              (c) =>
                                                                  c.id ===
                                                                  Number(
                                                                      vis.campaign,
                                                                  ),
                                                          )?.name
                                                        : "N/A"}
                                                </span>
                                                {loadingVisitImages ? (
                                                    <div className="w-full h-60 flex rounded-md flex-col items-center justify-center ">
                                                        <span className="text-xl font-semibold mb-12">
                                                            Loading images
                                                        </span>
                                                        <Spinner size="lg" />
                                                    </div>
                                                ) : (
                                                    <div
                                                        className={`grid grid-cols-2 gap-3 items-start place-items-center overflow-auto`}
                                                    >
                                                        <>
                                                            {visitImages?.map(
                                                                (img) => {
                                                                    return (
                                                                        <img
                                                                            key={
                                                                                img.id
                                                                            }
                                                                            src={
                                                                                "data:image/png;base64," +
                                                                                img.actual_image
                                                                            }
                                                                            alt={
                                                                                img.description
                                                                            }
                                                                            className="shadow-xl rounded-lg object-center object-contain w-full h-full"
                                                                        />
                                                                    );
                                                                },
                                                            )}
                                                        </>
                                                    </div>
                                                )}
                                                {vis.navigation_filename && (
                                                    <MapVisit
                                                        base64Data={
                                                            vis.navigation_actual_file ??
                                                            ""
                                                        }
                                                        station={station}
                                                    />
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </TableCard>
                </CardContainer>
            </div>

            {modals && modals?.title === "ConfirmDelete" && (
                <ConfirmDeleteModal
                    loading={loading}
                    msg={msg}
                    confirmRemove={() => delVisit()}
                    closeModal={() => {
                        setModals({
                            show: false,
                            title: "",
                            type: "edit",
                        });
                        setMsg(undefined);
                        getVisits();
                        getVisitsImages();
                        getCampaigns();
                    }}
                />
            )}

            {modals?.show && modals?.title === "AddVisit" && (
                <VisitAddModal
                    campaigns={campaigns}
                    campaignB={campaign}
                    setStateModal={setModals}
                    station={station}
                    closeModal={() => {
                        getVisits();
                        getVisitsImages();
                        getCampaigns();
                        setModals({
                            show: false,
                            title: "",
                            type: "edit",
                        });
                    }}
                    reFetch={() => {
                        getVisits();
                        getVisitsImages();
                        getCampaigns();
                    }}
                />
            )}
            {modals?.show && modals.title === "VisitDetail" && (
                <VisitDetailModal
                    campaigns={campaigns}
                    visitId={visit?.id}
                    setStateModal={setModals}
                    closeModal={() => {
                        getVisits();
                        getVisitsImages();
                        getCampaigns();
                        setVisit(undefined);
                    }}
                />
            )}
        </div>
    );
};

export default Visits;
