import { useEffect, useMemo, useState } from "react";
import {
    StationTypesModal,
    Pagination,
    Table,
    TableCard,
} from "@componentsReact";

import useApi from "@hooks/useApi";
import { useAuth } from "@hooks/useAuth";
import { showModal } from "@utils";

import { getStationTypesService } from "@services";

import { GetParams, StationStatus, StationStatusServiceData } from "@types";

const StationTypesTable = () => {
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

    const [loading, setLoading] = useState<boolean>(false);
    const [params, setParams] = useState<GetParams>(bParams);

    const [stationTypes, setStationTypes] = useState<StationStatus[]>([]);
    const [stationType, setStationType] = useState<StationStatus | undefined>(
        undefined,
    );

    const [activePage, setActivePage] = useState<number>(1);
    const [pages, setPages] = useState<number>(0);
    const PAGES_TO_SHOW = 2;
    const REGISTERS_PER_PAGE = 5; // Es el mismo que params.limit

    const getStationTypes = async () => {
        try {
            setLoading(true);
            const res = await getStationTypesService<StationStatusServiceData>(
                api,
                params,
            );
            setStationTypes(res.data);
            setPages(Math.ceil(res.total_count / bParams.limit));
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const paginateStationTypes = async (newParams: GetParams) => {
        try {
            setLoading(true);
            const res = await getStationTypesService<StationStatusServiceData>(
                api,
                newParams,
            );
            setStationTypes(res.data);
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
        paginateStationTypes(newParams);
    };

    const reFetch = () => {
        getStationTypes();
    };

    useEffect(() => {
        getStationTypes();
    }, []); // eslint-disable-line

    const titles = ["Name"];

    const body = useMemo(() => {
        return stationTypes
            ?.sort((a, b) => a.name.localeCompare(b.name))
            .map((st) =>
                Object.values({
                    // id: monument.id,
                    name: st.name,
                }),
            );
    }, [stationTypes]);

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);
    return (
        <TableCard
            title={"Station Types"}
            size={"650px"}
            addButtonTitle="+ Type"
            modalTitle="EditStationType"
            setModals={setModals}
            addButton={true}
        >
            <Table
                titles={body && body.length > 0 ? titles : []}
                body={body}
                table={"types"}
                loading={loading}
                dataOnly={false}
                onClickFunction={() =>
                    setModals({
                        show: true,
                        title: "EditStationType",
                        type: "edit",
                    })
                }
                setState={setStationType}
                state={stationTypes}
            />
            {body && body.length > 0 ? (
                <Pagination
                    pages={pages}
                    pagesToShow={PAGES_TO_SHOW}
                    activePage={activePage}
                    handlePage={handlePage}
                />
            ) : null}
            {modals?.show && modals.title === "EditStationType" && (
                <StationTypesModal
                    StationType={stationType}
                    modalType={modals.type}
                    setStateModal={setModals}
                    setStationType={setStationType}
                    reFetch={reFetch}
                />
            )}
        </TableCard>
    );
};

export default StationTypesTable;
