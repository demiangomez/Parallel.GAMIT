import { useEffect, useState } from "react";
import { Alert, FileAlert, FileDetails, Modal } from "@componentsReact";

import { useFormReducer } from "@hooks";
import useApi from "@hooks/useApi";
import { useAuth } from "@hooks/useAuth";

import {
    ErrorResponse,
    Errors,
    FileErrors,
    FilesErrorResponse,
    StationFilesData,
} from "@types";
import {
    patchStationMetaService,
    postStationsFilesAttachedService,
} from "@services";
import { apiOkStatuses } from "@utils";
import Pako from "pako";

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

    const { formState, dispatch } = useFormReducer({
        navigation_file: "",
        station: stationMetaId ?? undefined,
    });

    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: FileErrors } | undefined
    >(undefined);

    const [bMsg, setBMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

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

                let uploadedChunks = 0; // Fragmentos subidos globalmente
                const formData = new FormData();

                await Promise.all(
                    Object.values(files).map(async (value) => {
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
                    }),
                );

                const res = await postStationsFilesAttachedService<
                    StationFilesData | FilesErrorResponse
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

    // if meta is true, it means we are adding a navigation file to metadata,
    // else we are adding a attached file to metadata

    // if meta is true multiple input is false, else multiple input is true

    return (
        <Modal
            close={false}
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
                        title={
                            getInputTitle("navigation_file") ??
                            "Navigation File"
                        }
                        multiple={!meta}
                        className={` ${otherErrorBadge?.includes("navigation_file") ? "file-input-error" : ""} file-input file-input-bordered w-full `}
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
                                setProgressBar(false);
                                setMsg(undefined);
                                setBMsg(undefined);
                                const files = e.target.files;

                                if (files && files.length > 0) {
                                    Array.from(files).forEach(() => {
                                        handleChangeFiles(e.target);
                                    });
                                } else if (files && files.length === 0) {
                                    setFiles([]);
                                    setMsg(undefined);
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
                                            name: String(f.file.name),
                                        }}
                                        files={files}
                                        fileType={"other"}
                                        pageRecord={{
                                            pageType: "station",
                                            id: stationId ?? 0,
                                        }}
                                        msg={msg}
                                        setFiles={setFiles}
                                    />
                                ))}
                            </div>
                        </div>
                    )}
                </div>
                {progressBar && (
                    <div className="w-[500px] self-center text-center">
                        File upload progress
                        <progress
                            className="progress progress-success"
                            value={0}
                            max="100"
                        ></progress>
                        <span
                            id="progress-value"
                            className="font-semibold"
                        ></span>
                    </div>
                )}
                {!meta && <FileAlert msg={msg} />}
                {meta && <Alert msg={bMsg} />}
                {loading && (
                    <div className="w-full text-center">
                        <span className="loading loading-spinner loading-lg self-center"></span>
                    </div>
                )}

                <button
                    className="btn btn-success self-center w-3/12"
                    type="submit"
                    disabled={
                        progressBar ||
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

export default StationAddFileModal;
