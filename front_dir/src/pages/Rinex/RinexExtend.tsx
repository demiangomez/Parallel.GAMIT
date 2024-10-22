import { useState } from "react";
import { Alert, Modal } from "@componentsReact";

import { ArrowsUpDownIcon } from "@heroicons/react/24/outline";

import { useApi, useAuth } from "@hooks";
import { apiOkStatuses } from "@utils";

import { ErrorResponse, Errors, RinexData } from "@types";
import {
    postExtendDownRinexService,
    postExtendUpRinexService,
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
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [loading, setLoading] = useState<boolean>(false);

    const updateRinexUpwards = async () => {
        try {
            setLoading(true);
            if (rinex) {
                const res = await postExtendUpRinexService<
                    { statusCode: number } | ErrorResponse
                >(api, rinex.api_id);
                if ("status" in res) {
                    setMsg({
                        status: res.statusCode,
                        msg: res.response.type ?? res.msg,
                        errors: res.response,
                    });
                } else {
                    setMsg({
                        status: res.statusCode,
                        msg: "Rinex extended successfully",
                    });
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
                    { statusCode: number } | ErrorResponse
                >(api, rinex.api_id);
                if ("status" in res) {
                    setMsg({
                        status: res.statusCode,
                        msg: res.response.type ?? res.msg,
                        errors: res.response,
                    });
                } else {
                    setMsg({
                        status: res.statusCode,
                        msg: "Rinex extended successfully",
                    });
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const confirmExtend = () => {
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
