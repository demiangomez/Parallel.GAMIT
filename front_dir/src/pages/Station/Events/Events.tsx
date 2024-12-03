import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import {
    CardContainer,
    EventsDetail,
    EventsFilter,
    EventsTable,
    Pagination,
    TableCard,
} from "@componentsReact";

import { FunnelIcon, XMarkIcon } from "@heroicons/react/24/outline";

import { getStationEventsService } from "@services";
import { useAuth, useApi } from "@hooks";

import { showModal } from "@utils";
import { EVENTS_FILTERS_STATE } from "@utils/reducerFormStates";

import {
    GetParams,
    StationData,
    StationEvents,
    StationEventsData,
    StationMetadataServiceData,
} from "@types";

interface OutletContext {
    station: StationData;
    reStation: StationData;
    stationMeta: StationMetadataServiceData;
}

const Events = () => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const { station } = useOutletContext<OutletContext>();

    const filter = useMemo(() => {
        return {
            ...EVENTS_FILTERS_STATE,
            station_code: station.station_code,
            network_code: station.network_code,
        };
    }, []);

    const [loading, setLoading] = useState<boolean>(false);

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const [activePage, setActivePage] = useState<number>(1);
    const [pages, setPages] = useState<number>(0);
    const PAGES_TO_SHOW = 2;
    const REGISTERS_PER_PAGE = 8;

    const [events, setEvents] = useState<StationEvents[] | undefined>(
        undefined,
    );
    const [event, setEvent] = useState<StationEvents | undefined>(undefined);

    const [eventsFilter, setEventsFilter] = useState<boolean>(false);
    const [filters, setFilters] =
        useState<Record<keyof typeof EVENTS_FILTERS_STATE, any>>(filter);

    const getEvents = async () => {
        setLoading(true);
        try {
            const res = await getStationEventsService<StationEventsData>(api, {
                ...filters,
                offset: 0,
                limit: REGISTERS_PER_PAGE,
            });

            setEvents(res.data);
            setPages(Math.ceil(res.total_count / REGISTERS_PER_PAGE));
        } catch (e) {
            console.error(e);
        }
        setLoading(false);
    };

    const paginateEvents = async (newParams: GetParams) => {
        try {
            setLoading(true);

            for (const key in newParams) {
                if (newParams[key as keyof typeof newParams] === "") {
                    delete newParams[key as keyof typeof newParams];
                }
            }

            const res = await getStationEventsService<StationEventsData>(
                api,
                newParams,
            );

            setEvents(res.data);
            setPages(Math.ceil(res.total_count / REGISTERS_PER_PAGE));
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
                ...filters,
                limit: REGISTERS_PER_PAGE * 1,
                offset: REGISTERS_PER_PAGE * (page - 1),
            };
        } else {
            newParams = {
                ...filters,
                limit: REGISTERS_PER_PAGE,
                offset: REGISTERS_PER_PAGE * (page - 1),
            };
        }

        setActivePage(page);
        paginateEvents(newParams);
    };

    const onSubmit = () => {
        paginateEvents({
            ...filters,
            offset: 0,
            limit: REGISTERS_PER_PAGE,
        });
        setActivePage(1);
        setEventsFilter(true);
    };

    const handleCleanFilters = () => {
        paginateEvents({
            ...filter,
            offset: 0,
            limit: REGISTERS_PER_PAGE,
        });
        setFilters(filter);
        setActivePage(1);
        setEventsFilter(false);
    };

    useEffect(() => {
        getEvents();
    }, []);

    useEffect(() => {
        if (modals?.show) {
            showModal(modals.title);
        }
    }, [modals]);

    const titles = useMemo(() => {
        if (events) {
            if (events?.length === 0) return [];
            const keysToIgnore = ["event_id", "network_code", "station_code"];
            const keys = Object.keys(events[0]).filter(
                (key) => !keysToIgnore.includes(key),
            );
            return keys.map((key) => key.replace(/_/g, " "));
        }
    }, [events]);

    const body = useMemo(() => {
        if (events) {
            if (events?.length === 0) return [];

            return Object.values(events).map((event) => {
                const keysToIgnore = ["network_code", "station_code"];
                const keys = Object.keys(event).filter(
                    (key) => !keysToIgnore.includes(key),
                );
                return keys.map((key) => event[key as keyof typeof event]);
            });
        }
    }, [events]);

    return (
        <div className="">
            <h1 className="text-2xl font-base text-center">EVENTS</h1>

            <div className="flex flex-grow w-full justify-center pr-2 space-x-2 px-2 pb-4">
                <CardContainer title={""} height={false} addButton={false}>
                    <TableCard title="" size="100%">
                        <div className="w-full flex justify-end">
                            <button
                                className="btn self-end"
                                onClick={() =>
                                    setModals({
                                        show: true,
                                        title: "EventsFilter",
                                        type: "none",
                                    })
                                }
                            >
                                Filter
                                <FunnelIcon className="size-6" />
                            </button>
                            {eventsFilter && (
                                <button
                                    className="btn btn-error btn-circle absolute left-auto right-2"
                                    style={{
                                        width: "25px",
                                        height: "25px",
                                        minHeight: "10px",
                                    }}
                                    onClick={() => {
                                        setEventsFilter(false);
                                        setFilters(filter);
                                        paginateEvents({
                                            ...filter,
                                            offset: 0,
                                            limit: REGISTERS_PER_PAGE,
                                        });
                                        setActivePage(1);
                                        // setRinexFilterData(undefined);
                                        // setShouldFetchRinex(true); // Set the flag to fetch Rinex data
                                    }}
                                >
                                    <XMarkIcon className="size-5" />
                                </button>
                            )}
                        </div>

                        <EventsTable
                            events={events}
                            titles={titles ?? []}
                            body={body ?? []}
                            loading={loading}
                            onClickFunction={(row: StationEvents) => {
                                setEvent(row);
                                setModals({
                                    show: true,
                                    title: "EventsDetail",
                                    type: "none",
                                });
                            }}
                        />
                        {events && events?.length > 0 ? (
                            <Pagination
                                pages={pages}
                                pagesToShow={PAGES_TO_SHOW}
                                activePage={activePage}
                                handlePage={handlePage}
                            />
                        ) : null}
                    </TableCard>
                </CardContainer>
            </div>
            {modals?.show && modals.title === "EventsFilter" && (
                <EventsFilter
                    filters={filters}
                    setStateModal={setModals}
                    setFilters={setFilters}
                    onSubmit={() => {
                        onSubmit();
                    }}
                    handleCleanFilters={() => {
                        handleCleanFilters();
                    }}
                />
            )}
            {modals?.show && modals.title === "EventsDetail" && (
                <EventsDetail event={event} setStateModal={setModals} />
            )}
        </div>
    );
};

export default Events;
