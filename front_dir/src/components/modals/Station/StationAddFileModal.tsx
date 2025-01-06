import { useEffect, useState } from "react";
import { Alert, FileDetails, FileResultCard, Modal } from "@componentsReact";
import Pako from "pako";

import { useFormReducer, useApi, useAuth, useEscape } from "@hooks";

import { apiOkStatuses } from "@utils";

import {
    patchStationMetaService,
    postStationsFilesAttachedService,
} from "@services";

import {
    ErrorResponse,
    Errors,
    FileErrors,
    FilesErrorResponse,
    StationFilesData,
} from "@types";

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

    const defaultState = {
        navigation_file: "",
        station: stationMetaId ?? undefined,
    };

    const { formState, dispatch } = useFormReducer(defaultState);

    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);
    const [bMsg, setBMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [fileResults, setFileResults] = useState<
        { id: number; errors: FileErrors | undefined }[]
    >([]);

    const [globalDescription, setGlobalDescription] = useState<string>("");

    const [files, setFiles] = useState<
        { file: File; description: string; id: number; name?: string }[]
    >([]);

    const [progressBar, setProgressBar] = useState<boolean>(false);

    const addFile = async () => {
        try {
            setProgressBar(true);
            if (stationId) {
                const CHUNK_SIZE = 1024 * 1024 * 3; // 3MB por fragmento
                const totalChunks = Object.values(files).reduce(
                    (total, value) => {
                        const file = value.file;
                        return total + Math.ceil(file.size / CHUNK_SIZE);
                    },
                    0,
                );
                let res: StationFilesData | FilesErrorResponse | undefined =
                    undefined;
                let uploadedChunks = 0; // Fragmentos subidos globalmente
                await Promise.all(
                    Object.values(files).map(async (value) => {
                        const formData = new FormData();

                        const file = value.file;
                        const totalChunksByFile = Math.ceil(
                            file.size / CHUNK_SIZE,
                        );

                        for (let i = 0; i < totalChunksByFile; i++) {
                            // Fragmento del archivo
                            const start = i * CHUNK_SIZE;
                            const end = Math.min(start + CHUNK_SIZE, file.size);
                            const chunk = file.slice(start, end);

                            // Opcional: Comprimir el fragmento
                            const chunkBuffer = await chunk.arrayBuffer();
                            const compressedChunk = Pako.gzip(
                                new Uint8Array(chunkBuffer),
                            );

                            // FormData para enviar
                            formData.append(
                                "file",
                                new Blob([compressedChunk]),
                                `${value.file.name}.part${i + 1}`,
                            );
                            formData.append("description", value.description);
                            formData.append("station", stationId);

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

                        res = await postStationsFilesAttachedService<
                            StationFilesData | FilesErrorResponse
                        >(api, formData);

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
                                            errors: res.response.error_message,
                                        };

                                        return [...prev, errorWithId];
                                    }
                                    return prev;
                                });
                            } else {
                                const fileName = value.name ?? value.file.name;
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
                    setBMsg({
                        status: res.statusCode,
                        msg: res.response.type,
                        errors: res.response,
                    });
                } else if (res.statusCode === 200) {
                    setBMsg({
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
        if (meta) {
            if (otherErrorBadge?.includes(key)) {
                return bMsg?.errors?.errors.find((e) => e.attr === key)?.detail;
            } else return key;
        }
    };

    const otherErrorBadge = bMsg?.errors?.errors?.map((error) => error.attr);

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
        setMsg(undefined);
        setProgressBar(false);
        setBMsg(undefined);
        setFileResults([]);
        setFiles([]);
        setGlobalDescription("");
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
        if (
            !meta &&
            files.length === fileResults.length &&
            fileResults.length > 0
        ) {
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

    // if meta is true, it means we are adding a navigation file to metadata,
    // else we are adding a attached file to metadata

    // if meta is true multiple input is false, else multiple input is true

    return (
        <Modal
            close={true}
            modalId={"AddFile"}
            size={!meta ? "lg" : "sm"}
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
                        title={getInputTitle("navigation_file") ?? "File"}
                        multiple={!meta}
                        className={` ${otherErrorBadge?.includes("navigation_file") ? "file-input-error" : ""} file-input file-input-bordered w-full `}
                        onChange={(e) => {
                            defaultValues();

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
                                const files = e.target.files;

                                if (files && files.length > 0) {
                                    Array.from(files).forEach(() => {
                                        handleChangeFiles(e.target);
                                    });
                                } else if (files && files.length === 0) {
                                    setFiles([]);
                                    setGlobalDescription("");
                                }
                            }
                        }}
                    />
                    {!meta && (
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
                                        fileType={"other"}
                                        pageRecord={{
                                            pageType: "station",
                                            id: stationId ?? 0,
                                        }}
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
                {msg && !meta && <Alert msg={msg} />}
                {bMsg && meta && <Alert msg={bMsg} />}
                {loading && (
                    <div className="w-full text-center">
                        <span className="loading loading-spinner loading-lg self-center"></span>
                    </div>
                )}

                <button
                    className="btn btn-success self-center w-3/12"
                    type="submit"
                    disabled={
                        (!meta && files.length === 0) ||
                        progressBar ||
                        loading ||
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

export default StationAddFileModal;
