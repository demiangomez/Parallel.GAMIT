/* eslint-disable @typescript-eslint/no-unused-vars */

import { useOutletContext } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { Rnd } from "react-rnd";

import {
    CardContainer,
    Pagination,
    RinexAddModal,
    RinexExtendModal,
    RinexFilter,
    RinexTable,
    StationInfoModal,
    StatsModal,
    TableCard,
} from "@componentsReact";

import {
    BookmarkIcon,
    CheckCircleIcon,
    ExclamationCircleIcon,
    ExclamationTriangleIcon,
    FunnelIcon,
    XMarkIcon,
} from "@heroicons/react/24/outline";

import { useAuth, useApi } from "@hooks";

import { getRinexWithStatusService } from "@services";

import { showModal } from "@utils";
import {
    RinexData,
    RinexItem,
    RinexObject,
    RinexRelatedStationInfo,
    StationData,
    StationInfoData,
} from "@types";

type OutletContext = {
    station: StationData;
    showSidebar: boolean;
};

type CloseFunction = () => void;

const Actions = ({ close }: { close: CloseFunction }) => {
    return (
        <div className="grid grid-cols-1 grid-flow-dense gap-3 relative">
            <button
                type="button"
                onClick={() => close()}
                className="justify-self-end"
            >
                <XMarkIcon className="size-5" />
            </button>
            <div className="grid grid-cols-2 gap-3 grid-flow-dense text-lg w-full">
                <div className=" card border-[1px] p-4 border-neutral-300 flex flex-col space-y-2">
                    <span className="w-full flex justify-center font-bold text-xl">
                        Actions
                    </span>
                    <div className="flex flex-col break-words  space-y-4">
                        <span>
                            <strong>V</strong> = View (opens station information
                            record to view)
                        </span>
                        <span>
                            <strong>E</strong> = Edit
                        </span>
                        <span>
                            <strong>↧ ↥</strong> = Pull station info down/up to
                            cover
                        </span>
                        <span>
                            <strong>+</strong> = Add station information using
                            RINEX metadata
                        </span>
                    </div>
                </div>
                <div className="space-y-2 card border-[1px] p-4 border-neutral-300 flex flex-col">
                    <span className="font-bold text-xl flex justify-center ">
                        Status
                    </span>
                    <div className="flex flex-col space-y-4">
                        <div className="flex flex-col break-words items-center justify-center">
                            <ExclamationTriangleIcon className="size-7 fill-yellow-400" />{" "}
                            <span className="font-medium text-center">
                                Mismatch between RINEX metadata and station
                                information (see red-underlined fields)
                            </span>
                        </div>
                        <div className="flex flex-col break-words items-center justify-center">
                            <ExclamationCircleIcon className="size-7 fill-red-600" />

                            <span className="font-medium text-center">
                                Missing station information record
                            </span>
                        </div>
                        <div className="flex flex-col break-words items-center justify-center">
                            <CheckCircleIcon className="size-7 fill-green-500 " />
                            <span className="font-medium text-center">
                                Station information ok
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <div className="grid grid-cols-1 card p-4 border-[1px] space-y-2 items-center border-neutral-300  w-full">
                <span className="w-full flex justify-center font-bold text-xl">
                    Background color
                </span>
                <span>
                    <strong>RED</strong> ⇾ No station info
                </span>
                <span>
                    <strong>LIGHT RED</strong> ⇾ No station info but completion
                    &lt; 0.5
                </span>
                <span>
                    <strong>GRAY</strong> ⇾ Station info but completion &lt; 0.5
                </span>
                <span>
                    <strong>GREEN</strong> ⇾ All good
                </span>
            </div>
        </div>
    );
};

const Rinex = () => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const { station, showSidebar } = useOutletContext<OutletContext>();

    const [lastGroupIdPreviousPage, setLastGroupIdPreviousPage] = useState<
        string | undefined
    >(undefined);

    const [sameGroup, setSameGroup] = useState<boolean>(false);

    const [actionsManual, setActionsManual] = useState<boolean>(false);

    const [rinexCheckbox, setRinexCheckbox] = useState<boolean>(false);

    const [rinex, setRinex] = useState<RinexObject[] | undefined>(undefined);

    // BUTTON FIRST LEVEL
    const [rinexStationInfoRelated, setRinexStationInfoRelated] = useState<
        RinexRelatedStationInfo[] | undefined
    >(undefined);

    const [rinexGroup, setRinexGroup] = useState<RinexItem[] | undefined>(
        undefined,
    );

    const [rinexAddType, setRinexAddType] = useState<
        "file" | "metadata" | undefined
    >(undefined);

    // BUTTONS EXTEND RINEX SECOND LEVEL
    const [singleRinex, setSingleRinex] = useState<RinexData | undefined>(
        undefined,
    );

    const [extendTypeRinex, setExtendTypeRinex] = useState<
        "up" | "down" | undefined
    >(undefined);

    const [problematicRinex, setProblematicRinex] = useState<
        RinexObject[] | undefined
    >(undefined);

    const [paginatedRinexs, setPaginatedRinexs] = useState<
        RinexObject[] | undefined
    >(undefined);

    const [loading, setLoading] = useState<boolean>(false);

    const formattedTitles = (rinexs: RinexObject[]) => {
        const titles = rinexs?.[0]?.rinex[0]?.rinex[0] || {};

        const {
            has_station_info,
            has_multiple_station_info_gap,
            metadata_mismatch,
            gap_type,
            network_code,
            station_code,
            api_id,
            filtered,
            ...rest
        } = titles;

        const formattedTitles = Object.keys(rest).map((title) => {
            if (title.includes("observation")) {
                title = title.split("observation_").pop() || title;
            }
            return title.replace(/_/g, " ");
        });

        return formattedTitles;
    };

    const titles = formattedTitles(rinex ?? []);

    const REGISTERS_PER_PAGE = 15;

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const [activePage, setActivePage] = useState<number>(1);
    const [pages, setPages] = useState<number>(0);
    const PAGES_TO_SHOW = 2;

    const getRinex = async () => {
        try {
            setLoading(true);
            const res = await getRinexWithStatusService<RinexObject[]>(
                api,
                station.api_id ?? 0,
            );
            const rinexWithGroupId = res.map((item, index) => ({
                ...item,
                groupId: `group-${index}`,
            }));

            setRinex(rinexWithGroupId);

            const problematic = rinexWithGroupId
                .filter((rinex) =>
                    rinex.rinex.some((r) =>
                        r.rinex.some((r2) => !r2.has_station_info),
                    ),
                )
                .map((rinex) => ({
                    ...rinex,
                    rinex: rinex.rinex
                        .map((r) => ({
                            ...r,
                            rinex: r.rinex.filter((r2) => !r2.has_station_info),
                        }))
                        .filter((r) => r.rinex.length > 0),
                }))
                .filter((rinex) => rinex.rinex.length > 0);

            setProblematicRinex(problematic);
            setPages(Math.ceil(calculateTotalLength(res) / REGISTERS_PER_PAGE));
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const calculateTotalLength = (rinexs: RinexObject[]) => {
        return rinexs.reduce((total, item) => total + item.rinex.length, 0);
    };

    const paginateRinex = (rinexs: RinexObject[], page: number) => {
        const startIndex = (page - 1) * REGISTERS_PER_PAGE;
        const endIndex = startIndex + REGISTERS_PER_PAGE;
        let currentLength = 0;
        const paginated: RinexObject[] = [];
        let firstGroupId = null;
        let lastGroupId = null;

        for (let i = 0; i < rinexs.length; i++) {
            const item = rinexs[i];
            const itemLength = item.rinex.length;

            if (currentLength + itemLength > startIndex) {
                const start = Math.max(0, startIndex - currentLength);
                const end = Math.min(itemLength, endIndex - currentLength);
                const slicedRinex = item.rinex.slice(start, end);

                const groupedRinex = slicedRinex.map((rinexItem) => ({
                    ...rinexItem,
                    groupId: item.groupId,
                }));

                paginated.push({
                    ...item,
                    rinex: groupedRinex,
                });

                if (firstGroupId === null) {
                    firstGroupId = item.groupId;
                }

                if (currentLength + itemLength >= endIndex) {
                    lastGroupId = item.groupId;
                    break;
                }
            }

            currentLength += itemLength;
        }

        return { paginated, firstGroupId, lastGroupId };
    };

    const handlePage = (page: number) => {
        if (page < 1 || page > pages) return;

        const { paginated, firstGroupId, lastGroupId } = paginateRinex(
            rinexCheckbox ? problematicRinex ?? [] : rinex ?? [],
            page,
        );

        setActivePage(page);
        setPaginatedRinexs(paginated);

        if (page > activePage) {
            // Navegando hacia adelante
            if (
                lastGroupIdPreviousPage !== null &&
                firstGroupId === lastGroupIdPreviousPage
            ) {
                setSameGroup(true);
            } else {
                setSameGroup(false);
            }
        } else if (page !== 1) {
            // Navegando hacia atrás
            const { lastGroupId: lastGroupIdPreviousPage } = paginateRinex(
                rinexCheckbox ? problematicRinex ?? [] : rinex ?? [],

                page - 1,
            );
            if (
                lastGroupIdPreviousPage !== null &&
                firstGroupId === lastGroupIdPreviousPage
            ) {
                setSameGroup(true);
            } else {
                setSameGroup(false);
            }
        }

        setLastGroupIdPreviousPage(lastGroupId ?? "");
        setRinexStationInfoRelated(undefined);
    };

    const handleRinexCheckbox = () => {
        if (problematicRinex) {
            const { paginated, lastGroupId } = paginateRinex(
                problematicRinex,
                1,
            );
            setPaginatedRinexs(paginated);
            setLastGroupIdPreviousPage(lastGroupId ?? "");
            setPages(
                Math.ceil(
                    calculateTotalLength(problematicRinex) / REGISTERS_PER_PAGE,
                ),
            );
        }
    };

    useEffect(() => {
        if (station) {
            getRinex();
        }
    }, [station]); // eslint-disable-line

    useEffect(() => {
        if (rinex && !rinexCheckbox) {
            const { paginated, lastGroupId } = paginateRinex(rinex, 1);
            setPaginatedRinexs(paginated);
            setLastGroupIdPreviousPage(lastGroupId ?? "");
            setPages(
                Math.ceil(calculateTotalLength(rinex) / REGISTERS_PER_PAGE),
            );
        } else if (rinex && rinexCheckbox) {
            handleRinexCheckbox();
        }
    }, [rinex, rinexCheckbox]); // eslint-disable-line

    useEffect(() => {
        setActivePage(1);
    }, [rinexCheckbox]);

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    const rndOptions = {
        x: window.innerWidth / 2 - 370,
        y: window.innerHeight / 2 - 470,
        width: 620,
        height: 620,
    };

    const useStationInfoByRinexGroup = (
        rinexGroup: RinexItem[] | RinexData,
    ) => {
        return useMemo(() => {
            if (!rinexGroup) return {} as StationInfoData;
            // Verificamos si es un array
            if (Array.isArray(rinexGroup)) {
                const rinexGroupLastIndex = rinexGroup.length - 1;
                const rinexGroupLast = rinexGroup[rinexGroupLastIndex];
                const subRinexLastGroup =
                    rinexGroupLast?.rinex[rinexGroupLast?.rinex.length - 1];

                return {
                    api_id: subRinexLastGroup?.api_id ?? 0,
                    network_code: subRinexLastGroup?.network_code ?? "",
                    station_code: subRinexLastGroup?.station_code ?? "",
                    receiver_code: subRinexLastGroup?.receiver_type ?? "",
                    receiver_serial: subRinexLastGroup?.receiver_serial ?? "",
                    receiver_firmware: subRinexLastGroup?.receiver_fw ?? "",
                    antenna_code: subRinexLastGroup?.antenna_type ?? "",
                    antenna_serial: subRinexLastGroup?.antenna_serial ?? "",
                    antenna_height: String(
                        subRinexLastGroup?.antenna_offset ?? "",
                    ),
                    antenna_north: "",
                    antenna_east: "",
                    height_code: "",
                    radome_code: subRinexLastGroup?.antenna_dome,
                    date_start: subRinexLastGroup?.observation_s_time ?? "",
                    date_end: subRinexLastGroup?.observation_e_time ?? "",
                    receiver_vers: "",
                    comments:
                        "Record created based on file " +
                        subRinexLastGroup?.filename,
                } as StationInfoData;
            } else {
                // Si no es un array (RinexData), retornamos lo necesario según la estructura de RinexData
                return {
                    api_id: rinexGroup.api_id ?? 0,
                    network_code: rinexGroup.network_code ?? "",
                    station_code: rinexGroup.station_code ?? "",
                    receiver_code: rinexGroup.receiver_type ?? "",
                    receiver_serial: rinexGroup.receiver_serial ?? "",
                    receiver_firmware: rinexGroup.receiver_fw ?? "",
                    antenna_code: rinexGroup.antenna_type ?? "",
                    antenna_serial: rinexGroup.antenna_serial ?? "",
                    antenna_height: String(rinexGroup.antenna_offset ?? ""),
                    antenna_north: "",
                    antenna_east: "",
                    height_code: "",
                    radome_code: rinexGroup.antenna_dome,
                    date_start: rinexGroup.observation_s_time ?? "",
                    date_end: rinexGroup.observation_e_time ?? "",
                    receiver_vers: "",
                    comments:
                        "Record created based on data from " +
                        rinexGroup.filename,
                } as StationInfoData;
            }
        }, [rinexGroup]);
    };

    const stationInfoByRinex = useStationInfoByRinexGroup(
        rinexGroup ?? singleRinex ?? [],
    );

    console.log(
        "stationInfoByRinex",
        stationInfoByRinex,
        rinexGroup,
        singleRinex,
    );

    return (
        <div className="w-inherit flex flex-col items-center justify-center">
            {actionsManual && (
                <Rnd
                    default={rndOptions}
                    minWidth={620}
                    minHeight={400}
                    maxHeight={640}
                    bounds={"window"}
                    className="z-[1000] card border-[1px] border-neutral-300 shadow-2xl bg-base-100 p-4 overflow-y-auto overflow-x-hidden"
                >
                    <Actions close={() => setActionsManual(false)} />
                </Rnd>
            )}

            <h1 className="text-2xl font-base text-center">RINEX</h1>
            <div
                className="flex justify-center pr-2 px-2 pb-4 transition-all duration-200"
                style={{
                    width: `${showSidebar ? "calc(100vw - 20rem)" : "calc(100vw - 10rem)"}`,
                }}
            >
                <CardContainer title="" titlePosition="start">
                    <TableCard title={""} size="100%">
                        <div className="w-full flex">
                            <div className="w-2/4 flex justify-start">
                                <button
                                    className="hover:scale-110 transition-all duration-200"
                                    onClick={() =>
                                        setActionsManual(!actionsManual)
                                    }
                                >
                                    <BookmarkIcon className="size-6" />
                                </button>
                            </div>
                            <div className="w-2/4 flex justify-end space-x-2">
                                <label className="label cursor-pointer space-x-4">
                                    <span className="label-text">
                                        Rinex with problems
                                    </span>
                                    <input
                                        type="checkbox"
                                        className="checkbox"
                                        checked={rinexCheckbox}
                                        onChange={(e) =>
                                            setRinexCheckbox(e.target.checked)
                                        }
                                    />
                                </label>
                                <div className="h-12">
                                    <button
                                        className="btn self-end"
                                        onClick={() =>
                                            setModals({
                                                show: true,
                                                title: "RinexFilters",
                                                type: "none",
                                            })
                                        }
                                    >
                                        Filter
                                        <FunnelIcon className="size-6" />
                                    </button>
                                </div>
                            </div>
                        </div>

                        <RinexTable
                            titles={titles}
                            loading={loading}
                            sameGroup={sameGroup}
                            data={paginatedRinexs ?? []}
                            setModals={setModals}
                            setRinexStationInfoRelated={
                                setRinexStationInfoRelated
                            }
                            setRinexGroup={setRinexGroup}
                            setRinexAddType={setRinexAddType}
                            setSingleRinex={setSingleRinex}
                            setExtendTypeRinex={setExtendTypeRinex}
                        />
                        {rinex && rinex?.length > 0 && (
                            <Pagination
                                pages={pages}
                                pagesToShow={PAGES_TO_SHOW}
                                activePage={activePage}
                                handlePage={handlePage}
                            />
                        )}
                    </TableCard>
                </CardContainer>
            </div>
            {modals?.show && modals.title === "RinexFilters" && (
                <RinexFilter
                    setStateModal={setModals}
                    handleCloseModal={() => undefined}
                />
            )}

            {modals?.show && modals.title === "RinexAdd" && (
                <RinexAddModal
                    rinexGroup={rinexGroup}
                    singleRinex={singleRinex}
                    rinexAddType={rinexAddType}
                    closeModal={() => {
                        setModals({ show: false, title: "", type: "none" });
                        getRinex();
                        setRinexGroup(undefined);
                        setSingleRinex(undefined);
                        setRinexAddType(undefined);
                    }}
                    setModalState={setModals}
                    handleCloseModal={() => {
                        getRinex();
                        setRinexAddType(undefined);
                        setRinexGroup(undefined);
                        setSingleRinex(undefined);
                    }}
                />
            )}

            {modals?.show && modals.title === "RinexExtend" && (
                <RinexExtendModal
                    extendType={extendTypeRinex}
                    rinex={singleRinex}
                    closeModal={() => {
                        setModals({ show: false, title: "", type: "none" });
                        getRinex();
                    }}
                    handleCloseModal={() => getRinex()}
                    setModalState={setModals}
                />
            )}
            {modals?.show && modals.title === "Information" && (
                <StationInfoModal
                    close={false}
                    station={station}
                    size={"xl"}
                    rinexStationInfo={rinexStationInfoRelated ?? undefined}
                    setModalState={setModals}
                    refetch={() => {
                        setRinexStationInfoRelated(undefined);
                    }}
                />
            )}

            {modals?.show && modals?.title === "EditStats" && (
                <StatsModal
                    stationInfo={stationInfoByRinex}
                    modalType={modals.type}
                    reFetch={() => {
                        setActivePage(1);
                        getRinex();
                        setSingleRinex(undefined);
                        setRinexGroup(undefined);
                    }}
                    setStateModal={setModals}
                />
            )}
        </div>
    );
};

export default Rinex;
