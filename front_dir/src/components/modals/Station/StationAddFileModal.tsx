import { useState } from "react";
import { Alert, Modal } from "@componentsReact";

import { useFormReducer } from "@hooks";
import useApi from "@hooks/useApi";
import { useAuth } from "@hooks/useAuth";

import { ErrorResponse, Errors, StationFilesData } from "@types";
import {
    patchStationMetaService,
    postStationsFilesAttachedService,
} from "@services";
import { apiOkStatuses } from "@utils";

interface Props {
    stationId: string | undefined;
    stationMetaId?: string | undefined;
    meta: boolean;
    refetchStationMeta: () => void;
    reFetch: () => void;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
}

const StationAddFileModal = ({
    stationId,
    stationMetaId,
    meta,
    refetchStationMeta,
    reFetch,
    setStateModal,
}: Props) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [loading, setLoading] = useState<boolean>(false);

    const { formState, dispatch } = useFormReducer(
        meta
            ? { navigation_file: "", station: stationMetaId ?? undefined }
            : {
                  file: "",
                  filename: "",
                  description: "",
                  station: stationId ?? undefined,
              },
    );

    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const addFile = async () => {
        try {
            setLoading(true);
            if (stationId) {
                const formData = new FormData();

                Object.entries(formState).forEach(([key, value]) => {
                    if (value !== undefined) {
                        formData.append(key, value);
                    }
                });

                const res = await postStationsFilesAttachedService<
                    StationFilesData | ErrorResponse
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
                        msg: "File added successfully",
                    });
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const addMetaDataFile = async () => {
        try {
            setLoading(true);
            if (stationId) {
                const formData = new FormData();
                Object.entries(formState).forEach(([key, value]) => {
                    if (value !== undefined) {
                        if (key === "navigation_file") {
                            formData.append(key, value);
                        } else {
                            formData.append(key, value as string);
                        }
                    }
                });

                formData.append("navigation_file_delete", "false");

                const res = await patchStationMetaService<
                    StationFilesData | ErrorResponse
                >(api, Number(stationMetaId), formData);
                if (res.statusCode !== 200 && "status" in res) {
                    setMsg({
                        status: res.statusCode,
                        msg: res.response.type,
                        errors: res.response,
                    });
                } else if (res.statusCode === 200) {
                    setMsg({
                        status: res.statusCode,
                        msg: "File added successfully",
                    });
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleCloseModal = () => {
        meta ? refetchStationMeta() : reFetch();
    };

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        !meta ? addFile() : addMetaDataFile();
    };

    const errorBadge = msg?.errors?.errors?.map((error) => error.attr);

    return (
        <Modal
            close={false}
            modalId={"AddFile"}
            size={"sm"}
            handleCloseModal={() => handleCloseModal()}
            setModalState={setStateModal}
        >
            <div className="w-full flex grow mb-2">
                <h3 className="font-bold text-center text-2xl my-2 w-full self-center">
                    Add
                </h3>
            </div>
            <form className="form-control space-y-4" onSubmit={handleSubmit}>
                <div className="form-control space-y-2">
                    <input
                        type="file"
                        title={
                            errorBadge?.includes(
                                meta ? "navigation_file" : "file",
                            )
                                ? msg?.errors?.errors.find(
                                      (e) =>
                                          e.attr ===
                                          (meta ? "navigation_file" : "file"),
                                  )?.detail
                                : "File"
                        }
                        className={` ${errorBadge?.includes(meta ? "navigation_file" : "file") ? "file-input-error" : ""} file-input file-input-bordered w-full `}
                        onChange={(e) => {
                            if (meta) {
                                dispatch({
                                    type: "change_value",
                                    payload: {
                                        inputName: "navigation_file",
                                        inputValue:
                                            e.target.files &&
                                            e.target.files.length > 0
                                                ? e.target.files[0]
                                                : undefined,
                                    },
                                });
                            } else {
                                dispatch({
                                    type: "change_value",
                                    payload: {
                                        inputName: "file",
                                        inputValue:
                                            e.target.files &&
                                            e.target.files.length > 0
                                                ? e.target.files[0]
                                                : undefined,
                                    },
                                });
                                dispatch({
                                    type: "change_value",
                                    payload: {
                                        inputName: "filename",
                                        inputValue:
                                            e.target.files &&
                                            e.target.files.length > 0
                                                ? e.target.files[0].name
                                                : undefined,
                                    },
                                });
                            }
                        }}
                    />
                    {!meta && (
                        <label
                            className={`w-full input input-bordered flex items-center gap-2  ${errorBadge?.includes("description") ? "input-error" : ""}`}
                            title={
                                errorBadge?.includes("description")
                                    ? msg?.errors?.errors.find(
                                          (e) => e.attr === "description",
                                      )?.detail
                                    : "Description"
                            }
                        >
                            <div className="label">
                                <span className="font-bold">DESCRIPTION</span>
                            </div>
                            <input
                                type="text"
                                value={formState["description"]}
                                onChange={(e) => {
                                    dispatch({
                                        type: "change_value",
                                        payload: {
                                            inputName: "description",
                                            inputValue: e.target.value,
                                        },
                                    });
                                }}
                                className="grow "
                                autoComplete="off"
                            />
                        </label>
                    )}
                </div>
                <Alert msg={msg} />
                {loading && (
                    <div className="w-full text-center">
                        <span className="loading loading-spinner loading-lg self-center"></span>
                    </div>
                )}
                <button
                    className="btn btn-success self-center w-3/12"
                    disabled={
                        loading || apiOkStatuses.includes(Number(msg?.status))
                    }
                >
                    {" "}
                    Save{" "}
                </button>
            </form>
        </Modal>
    );
};

export default StationAddFileModal;
