import { useEffect, useState } from "react";
import { Alert, ConfirmDeleteModal, Modal } from "@componentsReact";

import { useApi, useAuth, useFormReducer } from "@hooks";
import {
    delStationCampaignService,
    patchStationCampaignService,
    postStationCampaignService,
} from "@services";

import { CampaignsData, ErrorResponse, Errors } from "@types";

import { apiOkStatuses, showModal } from "@utils";
import { CAMPAIGN_STATE } from "@utils/reducerFormStates";

interface Props {
    modalType: string;
    campaign: CampaignsData | undefined;
    reFetch: () => void;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
}

const AddCampaignModal = ({
    campaign,
    modalType,
    reFetch,
    setStateModal,
}: Props) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [loading, setLoading] = useState<boolean>(false);

    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const { formState, dispatch } = useFormReducer(CAMPAIGN_STATE);

    useEffect(() => {
        if (campaign) {
            dispatch({
                type: "set",
                payload: campaign,
            });
        }
    }, [campaign]);

    const addCampaign = async () => {
        try {
            setLoading(true);
            const res = await postStationCampaignService<any>(api, formState);
            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setMsg({
                    status: res.statusCode,
                    msg: "Campaign added successfully",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const delCampaign = async () => {
        try {
            setLoading(true);
            const res = await delStationCampaignService<ErrorResponse>(
                api,
                Number(campaign?.id),
            );
            if (res) {
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
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const editCampaign = async () => {
        try {
            setLoading(true);

            const res = await patchStationCampaignService<
                CampaignsData | ErrorResponse
            >(api, Number(campaign?.id), formState);
            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setMsg({
                    status: res.statusCode,
                    msg: "Campaign edited successfully",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleCloseModal = () => {
        reFetch();
    };

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();

        if (modalType === "edit") {
            await editCampaign();
        } else if (modalType === "add") {
            await addCampaign();
        }
    };

    const errorBadge = msg?.errors?.errors?.map((e) => e.attr);

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    return (
        <Modal
            close={false}
            modalId={"EditCampaigns"}
            size={"sm"}
            handleCloseModal={() => handleCloseModal()}
            setModalState={setStateModal}
        >
            <div className="w-full flex grow mb-2">
                <h3 className="font-bold text-center text-2xl my-2 w-full self-center">
                    {modalType?.charAt(0).toUpperCase() + modalType?.slice(1)}
                </h3>
            </div>
            <form className="form-control space-y-4" onSubmit={handleSubmit}>
                <div className="form-control space-y-2">
                    {Object.keys(formState || {}).map((key, index) => {
                        const disabled = key === "id";
                        const inputsToDatePicker = ["start_date", "end_date"];

                        return (
                            <div key={key + index} className="flex w-full">
                                <label
                                    key={index}
                                    className={`w-full input input-bordered flex items-center gap-2 ${
                                        errorBadge?.includes(key)
                                            ? "input-error"
                                            : ""
                                    } `}
                                    title={
                                        errorBadge?.includes(key)
                                            ? msg?.errors?.errors.find(
                                                  (e) => e.attr === key,
                                              )?.detail
                                            : formState[
                                                  key as keyof typeof formState
                                              ] ?? ""
                                    }
                                >
                                    <div className="label text-nowrap">
                                        <span className="font-bold">
                                            {key
                                                .toUpperCase()
                                                .replace("_", " ")
                                                .replace("_", " ")}
                                        </span>
                                    </div>
                                    <input
                                        type={
                                            inputsToDatePicker.includes(key)
                                                ? "date"
                                                : "text"
                                        }
                                        value={
                                            formState[
                                                key as keyof typeof formState
                                            ] ?? ""
                                        }
                                        onChange={(e) => {
                                            const value = e.target.value;
                                            dispatch({
                                                type: "change_value",
                                                payload: {
                                                    inputName: key,
                                                    inputValue: value,
                                                },
                                            });
                                        }}
                                        className="grow"
                                        autoComplete="off"
                                        placeholder={
                                            inputsToDatePicker.includes(key)
                                                ? "YYYY-MM-DD"
                                                : ""
                                        }
                                        disabled={disabled}
                                    />
                                    {errorBadge && errorBadge.includes(key) && (
                                        <span className="badge badge-error absolute right-0 mb-12 mr-2">
                                            {errorBadge.includes(key)
                                                ? msg?.errors?.errors.find(
                                                      (e) => e.attr === key,
                                                  )?.code
                                                : ""}
                                        </span>
                                    )}
                                </label>
                            </div>
                        );
                    })}
                </div>
                <Alert msg={msg} />
                {loading && (
                    <div className="w-full text-center">
                        <span className="loading loading-spinner loading-lg self-center"></span>
                    </div>
                )}
                <div className="flex w-full justify-center space-x-4">
                    {modalType === "edit" && (
                        <button
                            type="button"
                            className="btn btn-error w-3/12"
                            disabled={apiOkStatuses.includes(
                                Number(msg?.status),
                            )}
                            onClick={() =>
                                setModals({
                                    show: true,
                                    title: "ConfirmDelete",
                                    type: "edit",
                                })
                            }
                        >
                            Remove
                        </button>
                    )}
                    <button
                        className="btn btn-success self-center w-3/12"
                        disabled={
                            loading ||
                            apiOkStatuses.includes(Number(msg?.status))
                        }
                    >
                        {" "}
                        Save{" "}
                    </button>
                    {modals && modals?.title === "ConfirmDelete" && (
                        <ConfirmDeleteModal
                            msg={msg}
                            loading={loading}
                            confirmRemove={() => delCampaign()}
                            closeModal={() => {
                                setModals({
                                    show: false,
                                    title: "",
                                    type: "edit",
                                });
                            }}
                        />
                    )}
                </div>
            </form>
        </Modal>
    );
};

export default AddCampaignModal;
