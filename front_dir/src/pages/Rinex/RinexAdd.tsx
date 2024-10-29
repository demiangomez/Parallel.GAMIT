import { useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Alert, Modal } from "@componentsReact";

import { CloudArrowDownIcon } from "@heroicons/react/24/outline";

import { useAuth, useApi } from "@hooks";

import { postStationInfoByFileService } from "@services";
import { apiOkStatuses, formattedDates, woTz } from "@utils";
import { RinexAddFile, RinexFileResponse } from "@types";

interface Props {
    stationApiId: number;
    handleCloseModal: () => void;
    setModalState: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
}

interface DropzoneProps {
    file: File | undefined;
    setFile: React.Dispatch<React.SetStateAction<File | undefined>>;
}

const Dropzone = ({ file, setFile }: DropzoneProps) => {
    const { acceptedFiles, getRootProps, getInputProps } = useDropzone({
        maxFiles: 1,
    });

    useEffect(() => {
        if (acceptedFiles.length > 0) {
            setFile(acceptedFiles[0]);
        }
    }, [acceptedFiles, setFile]);

    return (
        <section className="w-full p-2">
            <div
                {...getRootProps({
                    className:
                        "w-full border-2 border-dashed cursor-pointer border-neutral-400 rounded-lg p-4 focus:border-violet-500 text-neutral-500",
                    style: {
                        flex: 1,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        padding: "20px",
                        backgroundColor: "#fafafa",
                        outline: "none",
                        transition: "border .24s ease-in-out",
                    },
                })}
            >
                <input {...getInputProps()} />
                {file ? (
                    <div>
                        <p>{file.name}</p>
                        <p>{file.size} bytes</p>
                    </div>
                ) : (
                    <>
                        <CloudArrowDownIcon className="size-10" />
                        <p>
                            Drag 'n' drop station info file, or click to select
                            file
                        </p>
                    </>
                )}
            </div>
        </section>
    );
};

const RinexAdd = ({ stationApiId, handleCloseModal, setModalState }: Props) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [loading, setLoading] = useState<boolean>(false);
    const [msg, setMsg] = useState<
        | {
              status: number;
              msg: string;
              errors?: RinexFileResponse;
              rinex_other_errors?: { [key: string]: string[] };
          }
        | undefined
    >(undefined);

    const [file, setFile] = useState<File | undefined>(undefined);

    const addFile = async () => {
        try {
            setLoading(true);
            const formData = new FormData();
            formData.append("file", file as File);

            const res = await postStationInfoByFileService<
                RinexAddFile | RinexFileResponse
            >(api, stationApiId, formData);

            if (res) {
                if ("status" in res) {
                    setMsg({
                        status: res.statusCode,
                        msg: "No station info created",
                        errors: res.response,
                    });
                } else if (
                    apiOkStatuses.includes(res.statusCode) &&
                    !("status" in res)
                ) {
                    const stationInfoInserted = res.inserted_station_info;

                    const errorMessage = res.error_message;

                    const formattedMsg = stationInfoInserted
                        .map(
                            (info) =>
                                `Station Code --> ${info.station_code?.toUpperCase()} \n Network Code --> ${info.network_code?.toUpperCase()} \n Date start --> ${formattedDates(woTz(new Date(info.date_start as string)) as Date)}`,
                        )
                        .join("\n");

                    setMsg({
                        status: res?.statusCode,
                        msg: `Station info successfully created\n${formattedMsg}`,
                        rinex_other_errors: errorMessage,
                    });
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Modal
            close={true}
            modalId={"RinexAdd"}
            size={"smPlus"}
            setModalState={setModalState}
            handleCloseModal={handleCloseModal}
        >
            <div className="flex p-2 items-center justify-center">
                <Dropzone file={file} setFile={setFile} />
            </div>

            <div className="w-full flex flex-col items-center mt-2">
                <button
                    className="btn btn-success w-[160px]"
                    type="button"
                    onClick={() => addFile()}
                    disabled={
                        !file ||
                        loading ||
                        apiOkStatuses.includes(Number(msg?.status))
                    }
                >
                    Add
                    {loading && (
                        <span className="loading loading-spinner loading-sm self-center"></span>
                    )}
                </button>
            </div>

            <div className="flex justify-center mt-4">
                {msg && <Alert msg={msg} />}
            </div>
        </Modal>
    );
};

export default RinexAdd;
