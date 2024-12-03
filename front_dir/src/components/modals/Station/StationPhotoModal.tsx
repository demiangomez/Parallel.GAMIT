import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { Modal, FileDetails, FileAlert } from "@componentsReact";

import ExifReader from "exifreader";

import { useAuth } from "@hooks/useAuth";
import useApi from "@hooks/useApi";

import { apiOkStatuses } from "@utils";
import { FileErrors, FilesErrorResponse, StationData } from "@types";
import { postStationsImagesService } from "@services";

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
    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: FileErrors } | undefined
    >(undefined);

    const [globalDescription, setGlobalDescription] = useState<string>("");

    const [files, setFiles] = useState<
        { file: File; description: string; id: number; name?: string }[]
    >([]);

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
            setLoading(true);

            const formData = new FormData();

            Object.values(files).forEach((value) => {
                formData.append("image", value.file);
                formData.append("name", value.name ?? value.file.name);
                formData.append("description", value.description);
                formData.append("station", String(station.api_id));
            });
            const res = await postStationsImagesService<
                any | FilesErrorResponse
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
                    msg: "Image added successfully",
                });
            }
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

    return (
        <Modal
            close={false}
            modalId={"AddStationPhoto"}
            size={"lg"}
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
                    <div className="form-control space-y-2">
                        <input
                            type="file"
                            multiple={true}
                            title={"File"}
                            className={` file-input file-input-bordered w-full `}
                            accept="image/*"
                            onChange={(e) => {
                                setMsg(undefined);
                                const files = e.target.files;
                                if (files && files.length > 0) {
                                    Array.from(files).forEach(() => {
                                        handleChangePhoto(e.target);
                                    });
                                } else if (files && files.length === 0) {
                                    setFiles([]);
                                    setMsg(undefined);
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
                                            fileType={"stationImages"}
                                            pageRecord={{
                                                pageType: "station",
                                                id: station.api_id ?? 0,
                                            }}
                                            // errorBadge={errorBadge}
                                            msg={msg}
                                            setFiles={setFiles}
                                        />
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
                <FileAlert msg={msg} />
                {loading && (
                    <div className="w-full text-center">
                        <span className="loading loading-spinner loading-lg self-center"></span>
                    </div>
                )}
                <div className="flex w-full justify-center space-x-4">
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
        </Modal>
    );
};

export default StationPhotoModal;
