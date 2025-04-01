import { useEffect, useState } from "react";
import { Alert, ConfirmDeleteModal, Modal } from "@componentsReact";
import {
    delMonumentTypesService,
    patchMonumentTypesService,
    postMonumentTypesService,
} from "@services";
import { useAuth, useApi, useFormReducer } from "@hooks";
import { apiOkStatuses, showModal } from "@utils";
import {
    Errors,
    ErrorResponse,
    ExtendedMonumentTypes,
    MonumentTypes,
} from "@types";

interface MonumentModalProps {
    Monument: MonumentTypes | undefined;
    modalType: string;
    reFetch: () => void;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
    setMonument: React.Dispatch<
        React.SetStateAction<MonumentTypes | undefined>
    >;
}

const MonumentModal = ({
    Monument,
    modalType,
    reFetch,
    setStateModal,
    setMonument,
}: MonumentModalProps) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const [loading, setLoading] = useState<boolean>(false);
    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [checks, setChecks] = useState<{ photo: boolean }>({ photo: false });

    const { formState, dispatch } = useFormReducer({
        id: "",
        name: "",
        photo_file: "",
    });

    useEffect(() => {
        if (Monument) {
            dispatch({
                type: "set",
                payload: Monument,
            });
        }
    }, [Monument]); // eslint-disable-line

    const postMonument = async () => {
        try {
            setLoading(true);

            const { id, ...data } = formState; // eslint-disable-line

            const formData = new FormData();

            formData.append("name", data.name);

            if (data.photo_file) {
                formData.append("photo_path", data.photo_file);
            }

            const res = await postMonumentTypesService<
                ExtendedMonumentTypes | ErrorResponse
            >(api, formData);
            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setMsg({
                    status: res.statusCode,
                    msg: "Monument added successfully",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const patchMonument = async () => {
        try {
            setLoading(true);

            const { id, ...data } = formState; // eslint-disable-line

            const formData = new FormData();

            formData.append("name", data.name);

            if (data.photo_file) {
                formData.append("photo_path", data.photo_file);
            }

            if (!checks?.photo) {
                formData.delete("photo_path");
            }

            const res = await patchMonumentTypesService<
                ExtendedMonumentTypes | ErrorResponse
            >(api, Number(Monument?.id), formData);
            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setMsg({
                    status: res.statusCode,
                    msg: "Monument edited successfully",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const delMonument = async () => {
        try {
            setLoading(true);

            const res = await delMonumentTypesService<ErrorResponse>(
                api,
                Number(Monument?.id),
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
        setMonument(undefined);
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
            patchMonument();
        } else if (modalType === "add") {
            postMonument();
        }
    };

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    return (
        <Modal
            close={false}
            modalId={"EditMonuments"}
            size={"smPlus"}
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
                        const errorBadge = msg?.errors?.errors?.find(
                            (error) => error.attr === key,
                        );
                        const optionalFields = ["photo_file"];
                        return (
                            <div
                                className="flex items-center gap-2"
                                key={key + index}
                            >
                                {key === "photo_file" ? (
                                    <div className="flex gap-2 items-center w-full">
                                        <input
                                            type="file"
                                            className="file-input file-input-bordered w-full"
                                            disabled={
                                                modalType === "edit" &&
                                                !checks?.photo
                                            }
                                            onChange={(e) => {
                                                dispatch({
                                                    type: "change_value",
                                                    payload: {
                                                        inputName: "photo_file",
                                                        inputValue:
                                                            e.target.files &&
                                                            e.target.files
                                                                .length > 0
                                                                ? e.target
                                                                      .files[0]
                                                                : undefined,
                                                    },
                                                });
                                            }}
                                        />
                                        {modalType === "edit" && (
                                            <input
                                                type="checkbox"
                                                className="checkbox"
                                                title={"Check to change photo"}
                                                checked={checks?.photo}
                                                onChange={() =>
                                                    setChecks((prev) => ({
                                                        ...prev,
                                                        photo: !prev?.photo,
                                                    }))
                                                }
                                            />
                                        )}
                                        {optionalFields.includes(key) && (
                                            <span className="badge badge-secondary">
                                                Optional
                                            </span>
                                        )}
                                    </div>
                                ) : (
                                    <label
                                        key={index}
                                        id={key}
                                        className={`w-full input input-bordered flex items-center gap-2 ${errorBadge ? "input-error" : ""}`}
                                        title={
                                            errorBadge ? errorBadge.detail : ""
                                        }
                                    >
                                        <div className="label">
                                            <span className="font-bold">
                                                {key
                                                    .toUpperCase()
                                                    .replace("_", " ")
                                                    .replace("_", " ")}
                                            </span>
                                        </div>
                                        <input
                                            type="text"
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
                                            disabled={key === "id"}
                                        />
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
                                )}
                            </div>
                        );
                    })}
                    {Monument && Monument?.photo_file && (
                        <div className="flex justify-center py-10">
                            <div className="card">
                                <div className="badge badge-accent gap-2 self-end -mb-4 z-[1]">
                                    last photo
                                </div>
                                <img
                                    className="object-cover"
                                    src={
                                        "data:image/*;base64," +
                                        Monument?.photo_file
                                    }
                                    alt={Monument?.name}
                                />
                            </div>
                        </div>
                    )}
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
                    confirmRemove={() => delMonument()}
                    closeModal={() => {
                        setModals({
                            show: false,
                            title: "",
                            type: "edit",
                        });
                        setMsg(undefined);
                    }}
                />
            )}
        </Modal>
    );
};

export default MonumentModal;
