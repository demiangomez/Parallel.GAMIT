import { useEffect, useMemo, useState } from "react";
import { StatsModal, Modal, Pagination, Table } from "@componentsReact";
import { PlusCircleIcon } from "@heroicons/react/24/outline";

import { getStationInfoService } from "@services";

import { useAuth } from "@hooks/useAuth";
import useApi from "@hooks/useApi";

import { showModal } from "@utils";

import {
    GetParams,
    RinexRelatedStationInfo,
    StationData,
    StationInfoData,
    StationInfoServiceData,
} from "@types";

interface StationInfoModalProps {
    close: boolean;
    size?: "sm" | "md" | "lg" | "xl" | "fit";
    rinexStationInfo?: RinexRelatedStationInfo[] | undefined;
    station?: StationData | undefined;
    setModalState: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
    refetch: () => void;
}

const StationInfoModal = ({
    close,
    station,
    rinexStationInfo,
    size,
    setModalState,
    refetch,
}: StationInfoModalProps) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [stationInfo, setStationInfo] = useState<StationInfoData | undefined>(
        undefined,
    );
    const [stationInfos, setStationInfos] = useState<
        StationInfoData[] | undefined
    >(undefined);

    const [loading, setLoading] = useState<boolean>(true);

    const {
        api_id, // eslint-disable-line
        network_code, // eslint-disable-line
        station_code, // eslint-disable-line
        ...restOfStationInfo
    } = stationInfos?.[0] || {};

    const titles = Object.keys(restOfStationInfo || {});
    const tableData = stationInfos?.map(
        ({
            api_id, // eslint-disable-line
            network_code, // eslint-disable-line
            station_code, // eslint-disable-line
            ...restOfStationInfo
        }: StationInfoData) => {
            return Object.values(restOfStationInfo);
        },
    );

    const REGISTERS_PER_PAGE = 15; // Es el mismo que params.limit

    const bParams: GetParams = useMemo(() => {
        return {
            network_code: station?.network_code,
            station_code: station?.station_code,
            limit: REGISTERS_PER_PAGE,
            offset: 0,
        };
    }, [station]);

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const [params, setParams] = useState<GetParams>(bParams);

    // PAGINATION... HEADACHE
    const [activePage, setActivePage] = useState<number>(1);
    const [pages, setPages] = useState<number>(0);
    const PAGES_TO_SHOW = 2;

    const getAllStationInfo = async (totalCount: number) => {
        let allData: StationInfoData[] = [];

        const newParams = {
            ...params,
            limit: 0,
            offset: totalCount,
        };

        const res = await getStationInfoService<StationInfoServiceData>(
            api,
            newParams,
        );

        allData = [...res.data];

        return allData;
    };

    const getStationInfo = async () => {
        try {
            setLoading(true);
            const res = await getStationInfoService<StationInfoServiceData>(
                api,
                bParams,
            );

            let allData = res.data;
            if (rinexStationInfo) {
                allData = await getAllStationInfo(res.total_count);
                allData = allData.filter((st) =>
                    rinexStationInfo.some((r) => r.api_id === st.api_id),
                );
            }

            const totalItems = rinexStationInfo
                ? allData.length
                : res.total_count;
            const totalPages = Math.ceil(totalItems / REGISTERS_PER_PAGE);

            setStationInfos(allData);
            setPages(totalPages);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const paginateStationInfo = async (newParams: GetParams) => {
        try {
            setLoading(true);
            const res = await getStationInfoService<StationInfoServiceData>(
                api,
                newParams,
            );

            let filteredData = res.data;
            if (rinexStationInfo) {
                filteredData = res.data.filter((st) =>
                    rinexStationInfo.some((r) => r.api_id === st.api_id),
                );
            }

            setStationInfos(filteredData);

            const totalItems = rinexStationInfo
                ? filteredData.length
                : res.total_count;
            const totalPages = Math.ceil(totalItems / REGISTERS_PER_PAGE);
            setPages(totalPages);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handlePage = (page: number) => {
        if (page < 1 || page > pages) return;

        const newParams = {
            ...params,
            limit: REGISTERS_PER_PAGE,
            offset: REGISTERS_PER_PAGE * (page - 1),
        };

        setParams(newParams);
        setActivePage(page);
        paginateStationInfo(newParams);
    };

    useEffect(() => {
        if (station && bParams.network_code && bParams.station_code) {
            getStationInfo();
        }
    }, [station]); // eslint-disable-line

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    return (
        <Modal
            close={close}
            modalId={"Information"}
            size={size}
            setModalState={setModalState}
            handleCloseModal={refetch}
        >
            <div className="w-full inline-flex">
                <h3 className="font-bold text-center text-3xl my-2 grow">
                    {station?.station_code.toUpperCase()}
                </h3>
                <label className="self-center">Add</label>
                <button
                    className="btn btn-ghost btn-circle ml-2"
                    onClick={() => {
                        setModals({
                            show: true,
                            title: "EditStats",
                            type: "add",
                        });
                        setStationInfo(undefined);
                    }}
                >
                    <PlusCircleIcon
                        strokeWidth={1.5}
                        stroke="currentColor"
                        className="w-8 h-10"
                    />
                </button>
            </div>

            <Table
                titles={titles}
                body={tableData}
                loading={loading}
                table={"Station"}
                dataOnly={false}
                onClickFunction={() => {
                    setModals({
                        show: true,
                        title: "EditStats",
                        type: "edit",
                    });
                }}
                setState={setStationInfo}
                state={stationInfos}
            />

            {stationInfos && stationInfos?.length > 0 && (
                <Pagination
                    pages={pages}
                    pagesToShow={PAGES_TO_SHOW}
                    activePage={activePage}
                    handlePage={handlePage}
                />
            )}
            {modals?.show && modals?.title === "EditStats" && (
                <StatsModal
                    stationInfo={stationInfo}
                    modalType={modals.type}
                    reFetch={() => {
                        setActivePage(1);
                        getStationInfo();
                    }}
                    setStateModal={setModals}
                    setStationInfo={setStationInfo}
                />
            )}
        </Modal>
    );
};

export default StationInfoModal;
