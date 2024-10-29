import { useEffect, useState } from "react";
import { Alert, Modal } from "@componentsReact";

import { ArrowsUpDownIcon } from "@heroicons/react/24/outline";

import { useApi, useAuth } from "@hooks";
import { apiOkStatuses } from "@utils";

import {
    ErrorResponse,
    Errors,
    ExtendedStationInfoData,
    RinexData,
    StationInfoData,
} from "@types";
import {
    getStationInfoByIdService,
    postExtendDownRinexService,
    postExtendUpRinexService,
    putStationInfoService,
} from "@services";

interface Props {
    extendType: "up" | "down" | undefined;
    rinex: RinexData | undefined;
    closeModal: () => void;
    handleCloseModal: () => void;
    setModalState: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
}

const RinexExtend = ({
    extendType,
    rinex,
    handleCloseModal,
    closeModal,
    setModalState,
}: Props) => {
    type StationInfoDataExtended = StationInfoData & {
        statusCode: number;
    };

    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [loading, setLoading] = useState<boolean>(false);

    const [stationInfoApiId, setStationInfoApiId] = useState<
        number | undefined
    >(undefined);

    const [stationInfo, setStationInfo] = useState<StationInfoData | undefined>(
        undefined,
    );

    const updateRinexUpwards = async () => {
        try {
            setLoading(true);
            if (rinex) {
                const res = await postExtendUpRinexService<
                    | { next_station_info_api_id: number; statusCode: number }
                    | ErrorResponse
                >(api, rinex.api_id);

                if ("status" in res) {
                    setMsg({
                        status: res.statusCode,
                        msg: res.response.type ?? res.msg,
                        errors: res.response,
                    });
                } else {
                    setStationInfoApiId(res.next_station_info_api_id);
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const updateRinexDownwards = async () => {
        try {
            setLoading(true);
            if (rinex) {
                const res = await postExtendDownRinexService<
                    | {
                          statusCode: number;
                          previous_station_info_api_id: number;
                      }
                    | ErrorResponse
                >(api, rinex.api_id);
                if ("status" in res) {
                    setMsg({
                        status: res.statusCode,
                        msg: res.response.type ?? res.msg,
                        errors: res.response,
                    });
                } else {
                    setStationInfoApiId(res.previous_station_info_api_id);
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const getStationInfoByApiId = async (apiId: number) => {
        try {
            setLoading(true);
            if (apiId) {
                const res = await getStationInfoByIdService<
                    StationInfoDataExtended | ErrorResponse
                >(api, apiId);

                if ("status" in res) {
                    setStationInfo(undefined);
                    setMsg({
                        status: res.statusCode,
                        msg: res.response.type ?? res.msg,
                        errors: res.response,
                    });
                } else {
                    setStationInfo(res);
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const putStationInfo = async () => {
        try {
            setLoading(true);

            const { observation_s_time, observation_e_time } = rinex ?? {};

            if (extendType === "up" && stationInfo) {
                stationInfo.date_start = observation_s_time ?? "";
            } else if (extendType === "down" && stationInfo) {
                stationInfo.date_end = observation_e_time ?? "";
            }

            const res = await putStationInfoService<
                ExtendedStationInfoData | ErrorResponse
            >(api, Number(stationInfo?.api_id), stationInfo ?? {});

            if (res) {
                if ("status" in res) {
                    setMsg({
                        status: res.statusCode,
                        msg: res.response.type,
                        errors: res.response,
                    });
                } else {
                    setMsg({
                        status: res.statusCode,
                        msg: "Station info extended successfully",
                    });
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (stationInfoApiId) {
            getStationInfoByApiId(stationInfoApiId);
        }
    }, [stationInfoApiId]);

    useEffect(() => {
        if (stationInfo) {
            putStationInfo();
        }
    }, [stationInfo]);

    const confirmExtend = () => {
        setStationInfoApiId(undefined);
        if (extendType === "up") {
            updateRinexUpwards();
        } else if (extendType === "down") {
            updateRinexDownwards();
        }
    };

    const closeModalExtended = () => {
        closeModal();
        setMsg(undefined);
    };

    return (
        <Modal
            close={true}
            modalId={"RinexExtend"}
            size={"smPlus"}
            setModalState={setModalState}
            handleCloseModal={handleCloseModal}
        >
            <div className="flex items-center justify-center">
                <div className="w-3/12">
                    <ArrowsUpDownIcon className={`size-20 `} />
                </div>
                <div className="w-9/12 flex flex-col">
                    <span className="text-xl font-bold">Are you sure?</span>
                    <span className="">
                        Are you sure you want to extend {extendType} this
                        Station Info file ?
                    </span>
                </div>
            </div>
            <div className="flex justify-center">
                {msg && <Alert msg={msg} />}
            </div>
            <div className="flex justify-center mt-6 space-x-4">
                <button
                    className="btn btn-success w-4/12"
                    type="button"
                    onClick={() => confirmExtend()}
                    disabled={
                        loading || apiOkStatuses.includes(Number(msg?.status))
                    }
                >
                    Extend
                    {loading && (
                        <span className="loading loading-spinner loading-sm self-center"></span>
                    )}
                </button>
                <button
                    className="btn btn-secondary w-4/12"
                    type="button"
                    onClick={() => closeModalExtended()}
                >
                    Close
                </button>
            </div>
        </Modal>
    );
};

export default RinexExtend;
