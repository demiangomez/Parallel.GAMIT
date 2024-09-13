import { useState } from "react";
import { Alert, Modal } from "@componentsReact";

import { useApi, useAuth, useFormReducer } from "@hooks";

import ExifReader from "exifreader";

import {
    patchStationVisitService,
    postStationVisitFilesService,
    postStationVisitGnssFilesService,
    postStationVisitsImagesService,
} from "@services";

import { apiOkStatuses } from "@utils";
import { ErrorResponse, Errors, VisitFilesData } from "@types";

interface Props {
    id: number | undefined;
    pageType: string;
    fileType: string;
    visit?: any;
    reFetch: () => void;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
}

const AddFileModal = ({
    id,
    pageType,
    fileType,
    visit,
    reFetch,
    setStateModal,
}: Props) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [loading, setLoading] = useState<boolean>(false);

    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const { formState, dispatch } = useFormReducer<
        Record<string, File | undefined | string | number>
    >({
        file: undefined,
        filename: "",
        description: "",
        name: "",
        [pageType]: id ?? undefined,
    });

    const handleChangePhoto = async (e: HTMLInputElement) => {
        const { files } = e;

        if (!files || files.length === 0) return;

        const file = files[0];
        try {
            const tags = await ExifReader.load(file, { async: true });

            if (tags.DateTimeOriginal) {
                const photoDatetime = tags.DateTimeOriginal?.description
                    .replace(" ", "_")
                    .replace(/:/g, "");
                dispatch({
                    type: "change_value",
                    payload: {
                        inputName: "name",
                        inputValue:
                            photoDatetime + "." + file.name.split(".").pop(),
                    },
                });
                dispatch({
                    type: "change_value",
                    payload: {
                        inputName: "image",
                        inputValue: file,
                    },
                });
            } else {
                const lastModifiedDate = new Date(file["lastModified"]);
                const formattedDate = `${lastModifiedDate.getFullYear()}${String(lastModifiedDate.getMonth() + 1).padStart(2, "0")}${String(lastModifiedDate.getDate()).padStart(2, "0")}_${String(lastModifiedDate.getHours()).padStart(2, "0")}${String(lastModifiedDate.getMinutes()).padStart(2, "0")}${String(lastModifiedDate.getSeconds()).padStart(2, "0")}`;
                dispatch({
                    type: "change_value",
                    payload: {
                        inputName: "name",
                        inputValue:
                            formattedDate + "." + file.name.split(".").pop(),
                    },
                });
                dispatch({
                    type: "change_value",
                    payload: {
                        inputName: "image",
                        inputValue: file,
                    },
                });
            }
        } catch (err) {
            console.error(err);
        }
    };

    const addFile = async () => {
        try {
            setLoading(true);
            if (pageType === "visit") {
                const formData = new FormData();

                if (fileType === "gnss" || fileType === "other") {
                    Object.entries(formState).forEach(([key, value]) => {
                        if (value !== undefined) {
                            if (key === "file") {
                                formData.append(key, value as File);
                            }
                            formData.append(key, value as string);
                        }
                    });

                    const service =
                        fileType === "gnss"
                            ? postStationVisitGnssFilesService
                            : postStationVisitFilesService;
                    const res = await service<VisitFilesData | ErrorResponse>(
                        api,
                        formData,
                    );

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

                if (fileType === "visitImage") {
                    Object.entries(formState).forEach(([key, value]) => {
                        if (value !== undefined) {
                            if (key === "file") {
                                formData.append(key, value as File);
                            }
                            formData.append(key, value as string);
                        }
                    });

                    const res = await postStationVisitsImagesService<
                        VisitFilesData | ErrorResponse
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

                if (fileType === "logsheet" || fileType === "navfile") {
                    try {
                        const formattedVisit = {
                            ...visit,
                            [fileType === "logsheet"
                                ? "log_sheet_file"
                                : "navigation_file"]:
                                formState[
                                    fileType === "logsheet"
                                        ? "log_sheet_file"
                                        : "navigation_file"
                                ],
                            [fileType === "logsheet"
                                ? "log_sheet_filename"
                                : "navigation_filename"]:
                                formState[
                                    fileType === "logsheet"
                                        ? "log_sheet_filename"
                                        : "navigation_filename"
                                ],
                        };

                        delete formattedVisit.log_sheet_actual_file;
                        delete formattedVisit.log_sheet_filename;
                        delete formattedVisit.navigation_actual_file;
                        delete formattedVisit.navigation_filename;

                        if (!formattedVisit.campaign)
                            delete formattedVisit.campaign;

                        Object.entries(formattedVisit).forEach(
                            ([key, value]) => {
                                if (key === "people" && Array.isArray(value)) {
                                    value?.forEach(
                                        (p: { id: number; name: string }) => {
                                            formData.append(
                                                "people",
                                                String(p.id),
                                            );
                                        },
                                    );
                                } else if (
                                    key === "log_sheet_file" ||
                                    (key === "navigation_file" &&
                                        value instanceof File)
                                ) {
                                    formData.append(key, value as File);
                                } else {
                                    formData.append(
                                        key,
                                        value as keyof typeof formState,
                                    );
                                }
                            },
                        );

                        const res =
                            await patchStationVisitService<ErrorResponse>(
                                api,
                                visit.id,
                                formData,
                            );
                        if ("status" in res) {
                            setMsg({
                                status: res.statusCode,
                                msg: res.response.type,
                                errors: res.response,
                            });
                        } else {
                            setMsg({
                                status: 200,
                                msg: "File updated successfully",
                            });
                        }
                    } catch (err) {
                        console.error(err);
                    } finally {
                        setLoading(false);
                    }
                }
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

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        addFile();
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
                            errorBadge?.includes("file")
                                ? msg?.errors?.errors.find(
                                      (e) => e.attr === "file",
                                  )?.detail
                                : "File"
                        }
                        className={` ${errorBadge?.includes("file") ? "file-input-error" : ""} file-input file-input-bordered w-full `}
                        onChange={(e) => {
                            {
                                fileType === "visitImage"
                                    ? handleChangePhoto(e.target)
                                    : dispatch({
                                          type: "change_value",
                                          payload: {
                                              inputName:
                                                  fileType === "logsheet"
                                                      ? "log_sheet_file"
                                                      : fileType === "navfile"
                                                        ? "navigation_file"
                                                        : fileType ===
                                                            "visitImage"
                                                          ? "image"
                                                          : "file",
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
                                        inputName:
                                            fileType === "logsheet"
                                                ? "log_sheet_filename"
                                                : fileType === "navfile"
                                                  ? "navigation_filename"
                                                  : "filename",
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
                    {fileType === "logsheet" ||
                    fileType === "navfile" ? null : fileType ===
                      "visitImage" ? (
                        <>
                            <label
                                className={`w-full input input-bordered flex items-center gap-2  ${errorBadge?.includes("name") ? "input-error" : ""}`}
                                title={
                                    errorBadge?.includes("name")
                                        ? msg?.errors?.errors.find(
                                              (e) => e.attr === "name",
                                          )?.detail
                                        : "Description"
                                }
                            >
                                <div className="label">
                                    <span className="font-bold">NAME</span>
                                </div>
                                <input
                                    type="text"
                                    value={formState["name"] as string}
                                    onChange={(e) => {
                                        dispatch({
                                            type: "change_value",
                                            payload: {
                                                inputName: "name",
                                                inputValue: e.target.value,
                                            },
                                        });
                                    }}
                                    className="grow "
                                    autoComplete="off"
                                />
                            </label>
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
                                    <span className="font-bold">
                                        DESCRIPTION
                                    </span>
                                </div>
                                <input
                                    type="text"
                                    value={formState["description"] as string}
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
                        </>
                    ) : (
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
                                value={formState["description"] as string}
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

export default AddFileModal;
