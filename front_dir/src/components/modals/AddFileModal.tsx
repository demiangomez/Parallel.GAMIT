import { useEffect, useState } from "react";
import { Alert, FileAlert, FileDetails, Modal } from "@componentsReact";

import { useApi, useAuth, useFormReducer } from "@hooks";

import ExifReader from "exifreader";

import {
    patchStationVisitService,
    postStationVisitFilesService,
    postStationVisitGnssFilesService,
    postStationVisitsImagesService,
} from "@services";

import { apiOkStatuses } from "@utils";
import {
    ErrorResponse,
    Errors,
    FileErrors,
    FilesErrorResponse,
    VisitFilesData,
} from "@types";

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
        { status: number; msg: string; errors?: FileErrors } | undefined
    >(undefined);

    const [bMsg, setBMsg] = useState<
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

    const [globalDescription, setGlobalDescription] = useState<string>("");

    const [files, setFiles] = useState<
        { file: File; description: string; id: number; name?: string }[]
    >([]);

    const getFileRecordKeys = () => {
        const filetype =
            fileType === "logsheet"
                ? "log_sheet_file"
                : fileType === "navfile"
                  ? "navigation_file"
                  : fileType === "visitImage"
                    ? "image"
                    : "file";

        const filename =
            fileType === "logsheet"
                ? "log_sheet_filename"
                : fileType === "navfile"
                  ? "navigation_filename"
                  : fileType === "visitImage"
                    ? "name"
                    : "filename";

        return { filetype, filename };
    };

    const handleChangePhoto = async (e: HTMLInputElement) => {
        const { files } = e;

        if (!files || files.length === 0) return;

        const newFiles = await Promise.all(
            Array.from(files).map(async (file, idx) => {
                try {
                    const tags = await ExifReader.load(file, { async: true });

                    if (tags.DateTimeOriginal) {
                        const photoDatetime = tags.DateTimeOriginal?.description
                            .replace(" ", "_")
                            .replace(/:/g, "");

                        return {
                            file,
                            description: "",
                            id: idx,
                            name:
                                photoDatetime +
                                "." +
                                file.name.split(".").pop(),
                        };
                    } else {
                        const lastModifiedDate = new Date(file["lastModified"]);
                        const formattedDate = `${lastModifiedDate.getFullYear()}${String(lastModifiedDate.getMonth() + 1).padStart(2, "0")}${String(lastModifiedDate.getDate()).padStart(2, "0")}_${String(lastModifiedDate.getHours()).padStart(2, "0")}${String(lastModifiedDate.getMinutes()).padStart(2, "0")}${String(lastModifiedDate.getSeconds()).padStart(2, "0")}`;

                        return {
                            file,
                            description: "",
                            id: idx,
                            name:
                                formattedDate +
                                "." +
                                file.name.split(".").pop(),
                        };
                    }
                } catch (err) {
                    console.error(err);
                    return {
                        file,
                        description: "",
                        id: idx,
                    };
                }
            }),
        );

        setFiles(newFiles);
    };

    const handleChangeFiles = (e: HTMLInputElement) => {
        const { files } = e;

        if (!files || files.length === 0) return;

        const newFiles = Array.from(files).map((file, idx) => {
            return {
                file,
                description: "",
                id: idx,
            };
        });

        setFiles(newFiles);
    };

    const addFile = async () => {
        try {
            setLoading(true);
            if (pageType === "visit") {
                const formData = new FormData();

                if (fileType === "gnss" || fileType === "other") {
                    Object.values(files).forEach((value) => {
                        const { filetype, filename } = getFileRecordKeys();
                        formData.append(filetype, value.file);
                        formData.append(filename, value.file.name);
                        formData.append("description", value.description);
                        formData.append(pageType, String(id));
                    });

                    const service =
                        fileType === "gnss"
                            ? postStationVisitGnssFilesService
                            : postStationVisitFilesService;
                    const res = await service<
                        VisitFilesData | FilesErrorResponse
                    >(api, formData);
                    if ("status" in res) {
                        setMsg({
                            status: res.statusCode,
                            msg: "",
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
                    Object.values(files).forEach((value) => {
                        const { filetype, filename } = getFileRecordKeys();
                        formData.append(filetype, value.file);
                        formData.append(
                            filename,
                            value.name ?? value.file.name,
                        );
                        formData.append("description", value.description);
                        formData.append(pageType, String(id));
                    });

                    const res = await postStationVisitsImagesService<
                        VisitFilesData | FilesErrorResponse
                    >(api, formData);

                    if ("status" in res) {
                        setMsg({
                            status: res.statusCode,
                            msg: "",
                            errors: res.response,
                        });
                    } else {
                        setMsg({
                            status: res.statusCode,
                            msg: "Images added successfully",
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
                            setBMsg({
                                status: res.statusCode,
                                msg: res.response.type,
                                errors: res.response,
                            });
                        } else {
                            setBMsg({
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

    useEffect(() => {
        if (globalDescription) {
            setFiles((prev) => {
                return prev.map((p) => {
                    return {
                        file: p.file,
                        description: globalDescription,
                        id: p.id,
                        name: p.name,
                    };
                });
            });
        }
    }, [globalDescription]);

    const getInputTitle = (key: string) => {
        if (!multipleFileTypes.includes(fileType)) {
            if (otherErrorBadge?.includes(key)) {
                return bMsg?.errors?.errors.find((e) => e.attr === key)?.detail;
            } else return key;
        }
    };

    const otherErrorBadge = bMsg?.errors?.errors?.map((error) => error.attr);

    const multipleFileTypes = ["gnss", "other", "visitImage"];

    return (
        <Modal
            close={false}
            modalId={"AddFile"}
            size={!multipleFileTypes.includes(fileType) ? "sm" : "lg"}
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
                        multiple={
                            fileType === "logsheet" || fileType === "navfile"
                                ? false
                                : true
                        }
                        title={getInputTitle(
                            fileType === "visitImage" ? "image" : "file",
                        )}
                        accept={fileType === "visitImage" ? "image/*" : "*"}
                        className={` ${otherErrorBadge?.includes("file") ? "file-input-error" : ""} file-input file-input-bordered w-full `}
                        onChange={(e) => {
                            setMsg(undefined);
                            setBMsg(undefined);
                            const files = e.target.files;
                            if (files && files.length > 0) {
                                Array.from(files).forEach((file) => {
                                    if (fileType === "visitImage") {
                                        handleChangePhoto(e.target);
                                    } else if (
                                        fileType === "gnss" ||
                                        fileType === "other"
                                    ) {
                                        handleChangeFiles(e.target);
                                    } else {
                                        dispatch({
                                            type: "change_value",
                                            payload: {
                                                inputName:
                                                    fileType === "logsheet"
                                                        ? "log_sheet_file"
                                                        : fileType === "navfile"
                                                          ? "navigation_file"
                                                          : "file",
                                                inputValue: file,
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
                                                inputValue: file.name,
                                            },
                                        });
                                    }
                                });
                            } else if (files && files.length === 0) {
                                setFiles([]);
                                setMsg(undefined);
                                setBMsg(undefined);
                                setGlobalDescription("");
                            }
                        }}
                    />
                    {multipleFileTypes.includes(fileType) && (
                        <label
                            className={`w-full input input-bordered flex items-center gap-2 `}
                            title={globalDescription}
                        >
                            <div className="label">
                                <span className="font-bold">
                                    GLOBAL DESCRIPTION
                                </span>
                            </div>
                            <input
                                type="text"
                                value={globalDescription}
                                onChange={(e) => {
                                    setGlobalDescription(e.target.value);
                                }}
                                disabled={files.length === 0}
                                className="grow "
                                autoComplete="off"
                            />
                        </label>
                    )}
                    {files && files.length > 0 && (
                        <div className="w-full">
                            <label className="label font-bold">FILES</label>
                            <div
                                className={`grid gap-4 grid-flow-dense w-full max-h-72 overflow-y-auto mt-6 pr-2 ${
                                    files.length === 1
                                        ? "grid-cols-1"
                                        : files.length === 2
                                          ? "grid-cols-2"
                                          : "grid-cols-3"
                                }`}
                            >
                                {Array.from(files).map((f) => (
                                    <FileDetails
                                        key={f.id}
                                        file={{
                                            id: String(f.id),
                                        }}
                                        files={files}
                                        fileType={fileType}
                                        pageRecord={{ pageType, id: id ?? 0 }}
                                        msg={msg}
                                        setFiles={setFiles}
                                    />
                                ))}
                            </div>
                        </div>
                    )}
                </div>
                {bMsg && <Alert msg={bMsg} />}
                {msg && <FileAlert msg={msg} />}
                {loading && (
                    <div className="w-full text-center">
                        <span className="loading loading-spinner loading-lg self-center"></span>
                    </div>
                )}
                <button
                    className="btn btn-success self-center w-3/12"
                    disabled={
                        loading ||
                        apiOkStatuses.includes(Number(msg?.status)) ||
                        apiOkStatuses.includes(Number(bMsg?.status))
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
