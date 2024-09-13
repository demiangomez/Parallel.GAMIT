import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { Modal, Alert } from "@componentsReact";

import ExifReader from "exifreader";

import { useAuth } from "@hooks/useAuth";
import useApi from "@hooks/useApi";
import { useFormReducer } from "@hooks";

import { apiOkStatuses } from "@utils";
import { Errors, StationData } from "@types";
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
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const { formState, dispatch } = useFormReducer({
        image: undefined,
        name: "",
        description: "",
    });

    const handleCloseModal = () => {
        return reFetch();
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

    const addPhoto = async () => {
        try {
            setLoading(true);

            const formData = new FormData();

            formData.append("station", String(station.api_id));

            Object.keys(formState).forEach((key) => {
                formData.append(key, formState[key as keyof typeof formState]);
            });
            const res = await postStationsImagesService<any>(api, formData);
            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
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

    return (
        <Modal
            close={false}
            modalId={"AddStationPhoto"}
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
                        const optionalFields = ["description"];
                        return (
                            <div
                                className="flex items-center gap-2"
                                key={key + index}
                            >
                                {key === "image" ? (
                                    <div className="flex gap-2 items-center w-full">
                                        <input
                                            type="file"
                                            name="img"
                                            className={` ${errorBadge && errorBadge?.attr === "image" ? "file-input-error" : ""} file-input file-input-bordered w-full `}
                                            onChange={(e) => {
                                                handleChangePhoto(e.target);
                                            }}
                                        />

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
                </div>
                <Alert msg={msg} />
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
