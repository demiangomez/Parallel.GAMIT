import { useEffect, useState } from "react";
import { Alert, FileDetails, FileResultCard, Modal } from "@componentsReact";

import { useApi, useAuth, useEscape, useFormReducer } from "@hooks";

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
import Pako from "pako";

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

    const [bMsg, setBMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const defaultState = {
        file: undefined,
        filename: "",
        description: "",
        name: "",
        [pageType]: id ?? undefined,
    };

    const { formState, dispatch } =
        useFormReducer<Record<string, File | undefined | string | number>>(
            defaultState,
        );

    const [globalDescription, setGlobalDescription] = useState<string>("");

    const [files, setFiles] = useState<
        { file: File; description: string; id: number; name?: string }[]
    >([]);

    const [fileResults, setFileResults] = useState<
        { id: number; errors: FileErrors | undefined }[]
    >([]);

    const [progressBar, setProgressBar] = useState<boolean>(false);

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
            if (pageType === "visit") {
                const formData = new FormData();
                const CHUNK_SIZE = 1024 * 1024 * 3; // 3MB por fragmento
                const totalChunks = Object.values(files).reduce(
                    (total, value) => {
                        const file = value.file;
                        return total + Math.ceil(file.size / CHUNK_SIZE);
                    },
                    0,
                );

                let res: VisitFilesData | FilesErrorResponse | undefined =
                    undefined;

                let uploadedChunks = 0; // Fragmentos subidos globalmente

                if (fileType === "gnss" || fileType === "other") {
                    setProgressBar(true);

                    await Promise.all(
                        Object.values(files).map(async (value) => {
                            const formDataByFile = new FormData();
                            const { filetype } = getFileRecordKeys();

                            const file = value.file;
                            const totalChunksByFile = Math.ceil(
                                file.size / CHUNK_SIZE,
                            );

                            for (let i = 0; i < totalChunksByFile; i++) {
                                // Fragmento del archivo
                                const start = i * CHUNK_SIZE;
                                const end = Math.min(
                                    start + CHUNK_SIZE,
                                    file.size,
                                );
                                const chunk = file.slice(start, end);

                                // Opcional: Comprimir el fragmento
                                const chunkBuffer = await chunk.arrayBuffer();
                                const compressedChunk = Pako.gzip(
                                    new Uint8Array(chunkBuffer),
                                );

                                // FormData para enviar
                                formDataByFile.append(
                                    filetype,
                                    new Blob([compressedChunk]),
                                    `${value.file.name}.part${i + 1}`,
                                );
                                formDataByFile.append(
                                    "description",
                                    value.description,
                                );
                                formDataByFile.append(pageType, String(id));

                                // Actualiza progreso
                                uploadedChunks++;
                                const progress = Math.min(
                                    (uploadedChunks / totalChunks) * 100,
                                    100,
                                );

                                document.querySelector("progress")!.value =
                                    progress;

                                document.getElementById(
                                    "progress-value",
                                )!.innerText = `${progress.toFixed(0)}%`;

                                progress === 100 && setLoading(true);
                            }

                            const service =
                                fileType === "gnss"
                                    ? postStationVisitGnssFilesService
                                    : postStationVisitFilesService;
                            res = await service<
                                VisitFilesData | FilesErrorResponse
                            >(api, formDataByFile);
                            if (res) {
                                if ("status" in res) {
                                    setFileResults((prev: any[]) => {
                                        if (
                                            res &&
                                            "status" in res &&
                                            res.response
                                        ) {
                                            const errorWithId = {
                                                id: value.id,
                                                errors: res.response
                                                    .error_message,
                                            };

                                            return [...prev, errorWithId];
                                        }
                                        return prev;
                                    });
                                } else {
                                    const fileName =
                                        value.name ?? value.file.name;
                                    setFileResults((prev: any[]) => {
                                        if (res) {
                                            const errorWithId = {
                                                id: value.id,
                                                errors: {
                                                    [fileName]: {
                                                        success: [
                                                            "File added successfully",
                                                        ],
                                                    },
                                                },
                                            };

                                            return [...prev, errorWithId];
                                        }
                                        return prev;
                                    });
                                }
                            }
                        }),
                    );
                }

                if (fileType === "visitImage") {
                    setProgressBar(true);

                    await Promise.all(
                        Object.values(files).map(async (value) => {
                            const formDataByFile = new FormData();

                            const { filetype, filename } = getFileRecordKeys();

                            const file = value.file;
                            const totalChunksByFile = Math.ceil(
                                file.size / CHUNK_SIZE,
                            );

                            for (let i = 0; i < totalChunksByFile; i++) {
                                // Fragmento del archivo
                                const start = i * CHUNK_SIZE;
                                const end = Math.min(
                                    start + CHUNK_SIZE,
                                    file.size,
                                );
                                const chunk = file.slice(start, end);

                                // Opcional: Comprimir el fragmento
                                const chunkBuffer = await chunk.arrayBuffer();
                                const compressedChunk = Pako.gzip(
                                    new Uint8Array(chunkBuffer),
                                );

                                // FormData para enviar
                                formDataByFile.append(
                                    filetype,
                                    new Blob([compressedChunk]),
                                    `${value.name}.part${i + 1}`,
                                );
                                formDataByFile.append(
                                    filename,
                                    value.name ?? value.file.name,
                                );
                                formDataByFile.append(
                                    "description",
                                    value.description,
                                );
                                formDataByFile.append(pageType, String(id));

                                // Actualiza progreso
                                uploadedChunks++;
                                const progress = Math.min(
                                    (uploadedChunks / totalChunks) * 100,
                                    100,
                                );

                                document.querySelector("progress")!.value =
                                    progress;

                                document.getElementById(
                                    "progress-value",
                                )!.innerText = `${progress.toFixed(0)}%`;

                                progress === 100 && setLoading(true);
                            }

                            res = await postStationVisitsImagesService<
                                VisitFilesData | FilesErrorResponse
                            >(api, formDataByFile);

                            if (res) {
                                if ("status" in res) {
                                    setFileResults((prev: any[]) => {
                                        if (
                                            res &&
                                            "status" in res &&
                                            res.response
                                        ) {
                                            const errorWithId = {
                                                id: value.id,
                                                errors: res.response
                                                    .error_message,
                                            };

                                            return [...prev, errorWithId];
                                        }
                                        return prev;
                                    });
                                } else {
                                    const fileName =
                                        value.name ?? value.file.name;
                                    setFileResults((prev: any[]) => {
                                        if (res) {
                                            const errorWithId = {
                                                id: value.id,
                                                errors: {
                                                    [fileName]: {
                                                        success: [
                                                            "Image added successfully",
                                                        ],
                                                    },
                                                },
                                            };

                                            return [...prev, errorWithId];
                                        }
                                        return prev;
                                    });
                                }
                            }
                        }),
                    );
                }

                if (fileType === "logsheet" || fileType === "navfile") {
                    try {
                        setLoading(true);

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

    const hasErrorMessage = fileResults.some(
        (result) =>
            result.errors &&
            Object.values(result.errors).some((error) => !error.success),
    );

    const hasSuccessMessage = fileResults.some(
        (result) =>
            result.errors &&
            Object.values(result.errors).some((error) => error.success),
    );

    const defaultValues = () => {
        setBMsg(undefined);
        setMsg(undefined);
        setGlobalDescription("");
        setProgressBar(false);
        setFileResults([]);
        setFiles([]);
    };

    const closeModal = () => {
        defaultValues();

        dispatch({
            type: "set",
            payload: defaultState,
        });
        handleCloseModal();
        const fileInputElement = document.getElementById(
            "file-input",
        ) as HTMLInputElement;
        if (fileInputElement) {
            fileInputElement.value = "";
        }
    };

    useEscape(closeModal);

    useEffect(() => {
        if (files.length === fileResults.length && fileResults.length > 0) {
            if (hasErrorMessage && !hasSuccessMessage) {
                setMsg({
                    status: 400,
                    errors: {
                        errors: [
                            {
                                code: "400",
                                attr: "files",
                                detail: "",
                            },
                        ],
                        type: "error",
                    },
                    msg: "Files were not uploaded successfully",
                });
            } else if (!hasErrorMessage && hasSuccessMessage) {
                setMsg({
                    status: 200,
                    msg: "Files uploaded successfully",
                });
            } else if (hasErrorMessage && hasSuccessMessage) {
                setMsg({
                    status: 199,
                    msg: "Some files were uploaded successfully but some failed",
                });
            }
        }
    }, [files, fileResults, hasErrorMessage, hasSuccessMessage]);

    return (
        <Modal
            close={true}
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
                        id="file-input"
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
                            defaultValues();

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
                                setProgressBar(false);
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
                    {files && files.length > 0 && fileResults.length === 0 && (
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
                                            name: String(f.file.name),
                                        }}
                                        files={files}
                                        fileType={fileType}
                                        pageRecord={{ pageType, id: id ?? 0 }}
                                        fileResults={fileResults}
                                        setFiles={setFiles}
                                    />
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                <FileResultCard fileResults={fileResults} />

                {progressBar && (
                    <div className="w-8/12 self-center text-center">
                        File upload progress
                        <progress
                            className={`progress ${fileResults.length > 0 ? (hasErrorMessage && !hasSuccessMessage ? "progress-error" : hasErrorMessage && hasSuccessMessage ? "progress-warning" : "progress-success") : "progress-success"}`}
                            value={0}
                            max="100"
                        ></progress>
                        <span
                            id="progress-value"
                            className="font-semibold"
                        ></span>
                    </div>
                )}
                {msg && <Alert msg={msg} />}
                {bMsg && <Alert msg={bMsg} />}
                {loading && (
                    <div className="w-full text-center">
                        <span className="loading loading-spinner loading-lg self-center"></span>
                    </div>
                )}
                <button
                    className="btn btn-success self-center w-3/12"
                    disabled={
                        (fileType !== "logsheet" &&
                            fileType !== "navfile" &&
                            files.length === 0) ||
                        progressBar ||
                        loading ||
                        apiOkStatuses.includes(Number(bMsg?.status)) ||
                        fileResults.length > 0
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