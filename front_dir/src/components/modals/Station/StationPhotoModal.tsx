import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { Modal, FileDetails, FileResultCard, Alert } from "@componentsReact";

// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import Pako from "pako";
import ExifReader from "exifreader";


import { useAuth, useApi } from "@hooks";

import { postStationsImagesService } from "@services";

import { Errors, FileErrors, FilesErrorResponse, StationData } from "@types";

interface Props {
    modalType: string;
    reFetch: () => void;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
}

interface OutletContext {
    station: StationData;
}

const StationPhotoModal = ({ modalType, reFetch, setStateModal }: Props) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const { station } = useOutletContext<OutletContext>();

    const [loading, setLoading] = useState<boolean>(false);
    const [globalDescription, setGlobalDescription] = useState<string>("");

    const [files, setFiles] = useState<
        { file: File; description: string; id: number; name?: string }[]
    >([]);

    const [msg, setMsg] = useState<{
        status: number;
        msg: string;
        errors?: Errors;
    } | null>(null);

    const [fileResults, setFileResults] = useState<
        { id: number; errors: FileErrors | undefined }[]
    >([]);

    const [progressBar, setProgressBar] = useState<boolean>(false);

    const handleCloseModal = () => {
        return reFetch();
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

    const addPhoto = async () => {
        try {
            setProgressBar(true);

            const CHUNK_SIZE = 1024 * 1024 * 3; // 3MB por fragmento
            const totalChunks = Object.values(files).reduce((total, value) => {
                const file = value.file;
                return total + Math.ceil(file.size / CHUNK_SIZE);
            }, 0);

            let res: any | FilesErrorResponse | undefined = undefined;

            let uploadedChunks = 0; // Fragmentos subidos globalmente

            await Promise.all(
                Object.values(files).map(async (value) => {
                    const formData = new FormData();

                    const file = value.file;
                    const totalChunksByFile = Math.ceil(file.size / CHUNK_SIZE);

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
                            "image",
                            new Blob([compressedChunk]),
                            `${value.name}.part${i + 1}`,
                        );
                        formData.append("name", value.name ?? value.file.name);
                        formData.append("description", value.description);
                        formData.append("station", String(station.api_id));

                        // Actualiza progreso
                        uploadedChunks++;
                        const progress = Math.min(
                            (uploadedChunks / totalChunks) * 100,
                            100,
                        );

                        document.querySelector("progress")!.value = progress;

                        document.getElementById("progress-value")!.innerText =
                            `${progress.toFixed(0)}%`;

                        progress === 100 && setLoading(true);
                    }
                    res = await postStationsImagesService<
                        any | FilesErrorResponse
                    >(api, formData);
                    if (res) {
                        if ("status" in res) {
                            setFileResults((prev: any[]) => {
                                if (res && "status" in res && res.response) {
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
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        addPhoto();
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
        setMsg(null);
        setGlobalDescription("");
        setProgressBar(false);
        setFileResults([]);
        setFiles([]);
    };

    const closeModal = () => {
        defaultValues();
        handleCloseModal();

        const fileInputElement = document.getElementById(
            "file-input",
        ) as HTMLInputElement;
        if (fileInputElement) {
            fileInputElement.value = "";
        }
    };

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
            modalId={"AddStationPhoto"}
            size={"lg"}
            handleCloseModal={() => closeModal()}
            setModalState={setStateModal}
        >
            <div className="w-full flex grow mb-2">
                <h3 className="font-bold text-center text-2xl my-2 w-full self-center">
                    {modalType?.charAt(0).toUpperCase() + modalType?.slice(1)}
                </h3>
            </div>
            <form className="form-control space-y-4" onSubmit={handleSubmit}>
                <div className="form-control space-y-2">
                    <div className="form-control space-y-2">
                        <input
                            type="file"
                            id="file-input"
                            multiple={true}
                            title={"File"}
                            className={` file-input file-input-bordered w-full `}
                            accept="image/*"
                            onChange={(e) => {
                                defaultValues();

                                const files = e.target.files;
                                if (files && files.length > 0) {
                                    Array.from(files).forEach(() => {
                                        handleChangePhoto(e.target);
                                    });
                                } else if (files && files.length === 0) {
                                    setFiles([]);
                                    setGlobalDescription("");
                                }
                            }}
                        />
                        <label
                            className={`w-full input input-bordered flex items-center gap-2 `}
                            title={"Description"}
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
                        {files &&
                            files.length > 0 &&
                            fileResults.length === 0 && (
                                <div className="w-full">
                                    <label className="label font-bold">
                                        FILES
                                    </label>
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
                                                fileType={"stationImages"}
                                                pageRecord={{
                                                    pageType: "station",
                                                    id: station.api_id ?? 0,
                                                }}
                                                fileResults={fileResults}
                                                setFiles={setFiles}
                                            />
                                        ))}
                                    </div>
                                </div>
                            )}
                    </div>
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
                {loading && (
                    <div className="w-full text-center">
                        <span className="loading loading-spinner loading-lg self-center"></span>
                    </div>
                )}
                <div className="flex w-full justify-center space-x-4">
                    <button
                        type="submit"
                        className="btn btn-success w-5/12"
                        disabled={files.length === 0 || loading || progressBar}
                    >
                        Submit
                    </button>
                </div>
            </form>
        </Modal>
    );
};

export default StationPhotoModal;
