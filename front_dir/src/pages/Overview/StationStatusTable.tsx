import { useEffect, useMemo, useState } from "react";
import {
    Pagination,
    Table,
    TableCard,
    StationStatusModal,
} from "@componentsReact";

import useApi from "@hooks/useApi";
import { useAuth } from "@hooks/useAuth";
import { showModal } from "@utils";

import { getStationStatusService } from "@services";
import { GetParams, StationStatus, StationStatusServiceData } from "@types";

const StationStatusTable = () => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const bParams: GetParams = useMemo(() => {
        return {
            limit: 5,
            offset: 0,
        };
    }, []);

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const [stationStatus, setStationStatus] = useState<
        StationStatus[] | undefined
    >(undefined);
    const [status, setStatus] = useState<StationStatus | undefined>(undefined);

    const [loading, setLoading] = useState<boolean>(false);
    const [params, setParams] = useState<GetParams>(bParams);

    const [activePage, setActivePage] = useState<number>(1);
    const [pages, setPages] = useState<number>(0);
    const PAGES_TO_SHOW = 2;
    const REGISTERS_PER_PAGE = 5; // Es el mismo que params.limit

    const getStationStatus = async () => {
        try {
            setLoading(true);
            const res = await getStationStatusService<StationStatusServiceData>(
                api,
                params,
            );
            setStationStatus(res.data);
            setPages(Math.ceil(res.total_count / bParams.limit));
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const paginateStationStatus = async (newParams: GetParams) => {
        try {
            setLoading(true);
            const res = await getStationStatusService<StationStatusServiceData>(
                api,
                newParams,
            );
            setStationStatus(res.data);
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
        paginateStationStatus(newParams);
    };

    const reFetch = () => {
        getStationStatus();
    };

    useEffect(() => {
        getStationStatus();
    }, []); // eslint-disable-line

    const titles = ["Name"];

    const body = useMemo(() => {
        return stationStatus
            ?.sort((a, b) => a.name.localeCompare(b.name))
            .map((st) =>
                Object.values({
                    // id: monument.id,
                    name: st.name,
                }),
            );
    }, [stationStatus]);

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    return (
        <TableCard
            title={"Station Status"}
            size={"650px"}
            addButton={true}
            modalTitle={"EditStationStatus"}
            setModals={setModals}
            addButtonTitle={"+ Status"}
        >
            <Table
                titles={body && body.length > 0 ? titles : []}
                body={body}
                table={"Station Status"}
                loading={loading}
                dataOnly={false}
                onClickFunction={() =>
                    setModals({
                        show: true,
                        title: "EditStationStatus",
                        type: "edit",
                    })
                }
                setState={setStatus}
                state={stationStatus}
            />
            {body && body.length > 0 ? (
                <Pagination
                    pages={pages}
                    pagesToShow={PAGES_TO_SHOW}
                    activePage={activePage}
                    handlePage={handlePage}
                />
            ) : null}
            {modals?.show && modals.title === "EditStationStatus" && (
                <StationStatusModal
                    StationStatus={status}
                    modalType={modals.type}
                    setStateModal={setModals}
                    setStationStatus={setStatus}
                    reFetch={reFetch}
                />
            )}
        </TableCard>
    );
};

export default StationStatusTable;
