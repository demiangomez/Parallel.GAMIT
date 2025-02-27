import { useEffect, useMemo, useState } from "react";
import {
    AddCampaignModal,
    Pagination,
    StationSelectModal,
    Table,
    TableCard,
} from "@componentsReact";

import useApi from "@hooks/useApi";
import { useAuth } from "@hooks/useAuth";

import { showModal } from "@utils";
import {
    getStationCampaignsService,
    getStationService,
    getStationVisitsService,
} from "@services";
import {
    CampaignsData,
    CampaignsServiceData,
    ExtendedStationData,
    GetParams,
    StationData,
    StationVisitsData,
    StationVisitsServiceData,
} from "@types";

const CampaignsTable = () => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const [loading, setLoading] = useState<boolean>(false);

    const [visits, setVisits] = useState<StationVisitsData[] | undefined>(
        undefined,
    );

    const [stations, setStations] = useState<StationData[]>([]);

    const [campaigns, setCampaigns] = useState<CampaignsData[] | undefined>(
        undefined,
    );
    const [campaign, setCampaign] = useState<CampaignsData | undefined>(
        undefined,
    );

    const [campaignVisits, setCampaignVisits] = useState<
        Record<string, StationVisitsData[]>
    >({});

    const [activePage, setActivePage] = useState<number>(1);
    const [pages, setPages] = useState<number>(0);
    const PAGES_TO_SHOW = 2;
    const REGISTERS_PER_PAGE = 5; // Es el mismo que params.limit

    const bParams: GetParams = useMemo(() => {
        return {
            limit: REGISTERS_PER_PAGE,
            offset: 0,
        };
    }, []);

    const [params, setParams] = useState<GetParams>(bParams);

    const getCampaigns = async () => {
        try {
            setLoading(true);
            const res = await getStationCampaignsService<CampaignsServiceData>(
                api,
                bParams,
            );
            setCampaigns(res.data);

            if(bParams.limit){
                setPages(Math.ceil(res.total_count / bParams.limit));
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const getVisits = async () => {
        try {
            setLoading(true);
            const res = await getStationVisitsService<StationVisitsServiceData>(
                api,
                {
                    limit: 0,
                    offset: 0,
                },
            );

            if (res.statusCode === 200) {
                setVisits(res.data);

                const uniqueStationIds = Array.from(
                    new Set(res.data.map((visit) => visit.station)),
                );

                uniqueStationIds.forEach(async (stationId) => {
                    const station = await getStationById(stationId);
                    if (station) {
                        setStations((prevStations) => {
                            if (
                                !prevStations.some(
                                    (s) => s.api_id === station?.api_id,
                                )
                            ) {
                                return [...prevStations, station];
                            }
                            return prevStations;
                        });
                    }
                });
            }
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const getStationById = async (id: number) => {
        try {
            setLoading(true);
            const res = await getStationService<ExtendedStationData>(api, id);
            if (res.statusCode === 200) {
                return res;
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const paginateCampaigns = async (newParams: GetParams) => {
        try {
            setLoading(true);
            const res = await getStationCampaignsService<CampaignsServiceData>(
                api,
                newParams,
            );
            setCampaigns(res.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handlePage = (page: number) => {
        if (page < 1 || page > pages) return;
        let newParams;
        if (page === 1) {
            newParams = {
                ...params,
                limit: REGISTERS_PER_PAGE * 1,
                offset: REGISTERS_PER_PAGE * (page - 1),
            };
        } else {
            newParams = {
                ...params,
                limit: REGISTERS_PER_PAGE,
                offset: REGISTERS_PER_PAGE * (page - 1),
            };
        }

        setParams(newParams);
        setActivePage(page);
        paginateCampaigns(newParams);
    };

    const reFetch = () => {
        getCampaigns();
    };

    useEffect(() => {
        getVisits();
        getCampaigns();
    }, []); // eslint-disable-line

    useEffect(() => {
        if (campaigns && visits) {
            const newCampaignVisits: Record<string, StationVisitsData[]> = {};
            campaigns.forEach((campaign) => {
                newCampaignVisits[campaign.name + "/~/" + campaign.id] =
                    visits.filter(
                        (visit) => Number(visit.campaign) === campaign.id,
                    );

                newCampaignVisits[campaign.name + "/~/" + campaign.id].map(
                    (v) => {
                        const station = stations.find(
                            (s) => s.api_id === v.station,
                        );
                        v.station_formatted = station
                            ? station.network_code + "." + station.station_code
                            : "";

                        return v;
                    },
                );
            });

            setCampaignVisits(newCampaignVisits);
        }
    }, [campaigns, visits, stations]);

    const titles = ["Name", "Visit", "Start Date", "End Date"];

    const body = useMemo(() => {
        return campaigns?.map((campaign) => {
            const visit = visits?.find(
                (v) => Number(v.campaign) === campaign.id,
            );
            const visitStation = stations.find(
                (s) => s.api_id === visit?.station,
            );

            const visitRes = visitStation
                ? "(" +
                  visitStation?.network_code +
                  "." +
                  visitStation?.station_code +
                  ")" +
                  " - " +
                  visit?.date
                : "";
            return Object.values({
                name: campaign.name,
                visit: visitRes,
                start_date: campaign.start_date,
                end_date: campaign.end_date,
            });
        });
    }, [campaigns, visits, stations]);

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    return (
        <TableCard
            title={"Campaigns"}
            size={"800px"}
            addButtonTitle="+ Campaign"
            modalTitle="EditCampaigns"
            setModals={setModals}
            addButton={true}
        >
            <Table
                titles={body && body.length > 0 ? titles : []}
                body={body}
                alterInfo={campaignVisits}
                table={"Campaigns"}
                loading={loading}
                dataOnly={false}
                buttonRegister={true}
                onClickFunction={() =>
                    setModals({
                        show: true,
                        title: "EditCampaigns",
                        type: "edit",
                    })
                }
                onAlterClickFunction={() =>
                    setModals({
                        show: true,
                        title: "SelectStation",
                        type: "edit",
                    })
                }
                setState={setCampaign}
                state={campaigns}
            />
            {body && body.length > 0 ? (
                <Pagination
                    pages={pages}
                    pagesToShow={PAGES_TO_SHOW}
                    activePage={activePage}
                    handlePage={handlePage}
                />
            ) : null}
            {modals?.show && modals.title === "EditCampaigns" && (
                <AddCampaignModal
                    campaign={campaign}
                    modalType={modals.type}
                    setStateModal={setModals}
                    reFetch={() => {
                        reFetch();
                        setCampaign(undefined);
                    }}
                />
            )}

            {modals?.show && modals.title === "SelectStation" && (
                <StationSelectModal
                    campaign={campaign}
                    setStateModal={setModals}
                />
            )}
        </TableCard>
    );
};

export default CampaignsTable;
