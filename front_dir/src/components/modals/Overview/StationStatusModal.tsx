import { useEffect, useState } from "react";
import { Alert, ConfirmDeleteModal, Modal, ColorPickerModal } from "@componentsReact";
import { delStationStatusService, patchStationStatusService, postStationStatusService} from "@services";
import {useApi, useAuth, useFormReducer } from "@hooks";
import { apiOkStatuses, showModal } from "@utils";
import { Errors, ErrorResponse, ExtendedStationStatus, StationStatusData, ColorData} from "@types";

interface StationStatusModalProps {
    StationStatus: StationStatusData | undefined;
    modalType: string;
    reFetch: () => void;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
    setStationStatus: React.Dispatch<
        React.SetStateAction<StationStatusData | undefined>
    >;
    colores: ColorData[]
}

const StationStatusModal = ({
    StationStatus,
    modalType,
    reFetch,
    setStateModal,
    setStationStatus,
    colores,
}: StationStatusModalProps) => {
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

    const [showColorModal, setShowColorModal] = useState<
    | { show: boolean; title: string; type: "add" | "edit" | "none" }
    | undefined
    >(undefined);

    const { formState, dispatch } = useFormReducer({
        id: "",
        name: "",
        color: 1,
    });

    useEffect(() => {
        if (StationStatus) {
            dispatch({
                type: "set",
                payload: StationStatus,
            });
        }
    }, [StationStatus]); // eslint-disable-line


    const postStatus = async () => {
        try {
            setLoading(true);

            const { id, ...data } = formState; // eslint-disable-line

            const res = await postStationStatusService<
                ExtendedStationStatus | ErrorResponse
            >(api, data);
            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setMsg({
                    status: res.statusCode,
                    msg: "Station Status added successfully",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const patchStatus = async () => {
        try {
            setLoading(true);

            const { id, ...data } = formState; // eslint-disable-line

            const res = await patchStationStatusService<
                ExtendedStationStatus | ErrorResponse
            >(api, Number(StationStatus?.id), data);
            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setMsg({
                    status: res.statusCode,
                    msg: "Station Status edited successfully",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const delStatus = async () => {
        try {
            setLoading(true);

            const res = await delStationStatusService<ErrorResponse>(
                api,
                Number(StationStatus?.id),
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

    const handleCloseModal = () => {
        setStationStatus(undefined);
        reFetch();
    };

    const handleChange = (e: HTMLInputElement | HTMLSelectElement) => {
        const { name, value } = e;

        dispatch({
            type: "change_value",
            payload: {
                inputName: name,
                inputValue: value,
            },
        });
    };

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (modalType === "edit") {
            patchStatus();
        } else if (modalType === "add") {
            postStatus();
        }
    };

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    useEffect(() => {
        showColorModal?.show && showModal(showColorModal.title);
    }, [showColorModal]);

    useEffect(() => {
        if(modalType === "edit"){
            changeColorIdToString(formState.color);
        }
    },
    [formState])

    const [colorName, setColorName] = useState<string>("");

    const changeColorIdToString = (pickedColor: number) => {
        const color = colores.find((color) => color.id === pickedColor);
        if(color){
            const finalColor = color.color.replace('-icon', '').replace('-',' ').replace(color.color.charAt(0),color.color.charAt(0).toUpperCase())
            setColorName(finalColor);
        }
    }

    return (
        <Modal
            close={false}
            modalId={"EditStationStatus"}
            size={"fit"}
            handleCloseModal={() => handleCloseModal()}
            setModalState={setStateModal}
        >
            <div className="w-full flex grow mb-2">
                <h3 className="font-bold text-center text-2xl my-2 w-full self-center">
                    {modalType?.charAt(0).toUpperCase() + modalType?.slice(1)}
                </h3>
            </div>
            <form className="form-control space-y-4" onSubmit={handleSubmit}>
                <div className="flex flex-row justify-around items-start ">
                    <div className="form-control space-y-2 w-full px-4">
                        {Object.keys(formState || {}).map((key, index) => {
                            const errorBadge = msg?.errors?.errors?.find(
                                (error) => error.attr === key,
                            );
                            const optionalFields: string[] = [];
                            if(key !== "color_name"){
                                return (
                                    
                                    <div
                                        className="flex gap-2"
                                        key={key + index}
                                    >
                                        <label
                                            key={index}
                                            id={key}
                                            className={`w-full input input-bordered flex items-center gap-2 ${errorBadge ? "input-error" : ""}`}
                                            title={errorBadge ? errorBadge.detail : ""}
                                        >
                                            <div className="label">
                                                <span className="font-bold">
                                                    {key
                                                        .toUpperCase()
                                                        .replace("_", " ")
                                                        .replace("_", " ")}
                                                </span>
                                            </div>
                                            { key !== "color" &&
                                            <input
                                                type="text "
                                                name={key}
                                                value={
                                                    formState[
                                                        key as keyof typeof formState
                                                    ] ?? ""
                                                }
                                                onChange={(e) => {
                                                    handleChange(e.target);
                                                }}
                                                className="grow "
                                                autoComplete="off"
                                                disabled={key === "id" }
                                            />
                                            }
                                            {   key === "color" &&
                                            <>
                                                <input
                                                    type="text "
                                                    name={key}
                                                    value={
                                                        colorName
                                                    }
                                                    onChange={(e) => {
                                                        handleChange(e.target);
                                                    }}
                                                    className="grow "
                                                    autoComplete="off"
                                                />
                                                <a 
                                                    onClick={() => {
                                                        setShowColorModal({
                                                            show: true,
                                                            title: "ColorPicker",
                                                            type: "edit",
                                                        })
                                                    }}
                                                >
                                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-6">
                                                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.098 19.902a3.75 3.75 0 0 0 5.304 0l6.401-6.402M6.75 21A3.75 3.75 0 0 1 3 17.25V4.125C3 3.504 3.504 3 4.125 3h5.25c.621 0 1.125.504 1.125 1.125v4.072M6.75 21a3.75 3.75 0 0 0 3.75-3.75V8.197M6.75 21h13.125c.621 0 1.125-.504 1.125-1.125v-5.25c0-.621-.504-1.125-1.125-1.125h-4.072M10.5 8.197l2.88-2.88c.438-.439 1.15-.439 1.59 0l3.712 3.713c.44.44.44 1.152 0 1.59l-2.879 2.88M6.75 17.25h.008v.008H6.75v-.008Z" />
                                                    </svg>
                                                </a>
                                            </>
                                            }
                                            {errorBadge && (
                                                <span className="badge badge-error">
                                                    {errorBadge.code}
                                                </span>
                                            )}
                                            {optionalFields.includes(key) && (
                                                <span className="badge badge-secondary">
                                                    Optional
                                                </span>
                                            )}

                                            
                                        </label>
                                    </div>
                                );
                            }
                        })}
                    </div>
                </div>
                <div className="px-4">
                    <Alert msg={msg} />
                </div> 
                {loading && (
                    <div className="w-full text-center">
                        <span className="loading loading-spinner loading-lg self-center"></span>
                    </div>
                )}
                <div className="flex w-full justify-center space-x-4">
                    {modalType === "edit" && (
                        <button
                            className="btn btn-error w-5/12"
                            type="button"
                            disabled={
                                apiOkStatuses.includes(Number(msg?.status)) ||
                                loading
                            }
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
                        type="submit"
                        className="btn btn-success w-5/12"
                        disabled={
                            apiOkStatuses.includes(Number(msg?.status)) ||
                            loading
                        }
                    >
                        Submit
                    </button>
                </div>
            </form>
            {modals && modals?.title === "ConfirmDelete" && (
                <ConfirmDeleteModal
                    msg={msg}
                    loading={loading}
                    confirmRemove={() => delStatus()}
                    closeModal={() => {
                        setModals({
                            show: false,
                            title: "",
                            type: "edit",
                        });
                    }}
                />
            )}
            {showColorModal && showColorModal?.title === "ColorPicker" &&
                <ColorPickerModal dispatch={dispatch} 
                    closeModal={() => {
                        setShowColorModal({
                            show: false,
                            title: "",
                            type: "edit",
                        });
                    }}
                    colores = {colores}
                    changeColorIdToString={changeColorIdToString}
                    formstate={formState}
                    type={showColorModal.type}
                />   
            }
        </Modal>
    );
};

export default StationStatusModal;
