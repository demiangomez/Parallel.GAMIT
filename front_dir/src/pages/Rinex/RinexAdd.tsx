import { useDropzone } from "react-dropzone";
import { Modal } from "@componentsReact";

import { CloudArrowDownIcon } from "@heroicons/react/24/outline";

import { RinexData, RinexItem } from "@types";
import { useEffect, useState } from "react";

interface Props {
    rinexGroup: RinexItem[] | undefined;
    singleRinex: RinexData | undefined;
    rinexAddType: "file" | "metadata" | undefined;
    closeModal: () => void;
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

const RinexAdd = ({
    rinexGroup,
    singleRinex,
    rinexAddType,
    closeModal,
    handleCloseModal,
    setModalState,
}: Props) => {
    // console.log({ rinexGroup }, { singleRinex });

    const [file, setFile] = useState<File | undefined>(undefined);

    //TODO: ADD ES RINEXGROUP, EDIT ES SINGLERINEX

    return (
        <Modal
            close={true}
            modalId={"RinexAdd"}
            size={"smPlus"}
            setModalState={setModalState}
            handleCloseModal={handleCloseModal}
        >
            <div className="flex space-x-4 items-center justify-center">
                {" "}
                {rinexAddType === "file" ? (
                    <Dropzone file={file} setFile={setFile} />
                ) : (
                    rinexAddType === "metadata" && (
                        <div className="w-[45%]">
                            <button
                                className="btn btn-light w-full tracking-wide"
                                style={{ height: "120px", fontSize: "18px" }}
                            >
                                Add station info by rinex metadata
                            </button>
                        </div>
                    )
                )}
                {/* <div className="w-[45%]">
                    <button
                        className="btn btn-light w-full tracking-wide"
                        style={{ height: "120px", fontSize: "18px" }}
                    >
                        Add station info by {rinexGroup ? "first" : ""} rinex
                        metadata
                    </button>
                </div> */}
            </div>
            {rinexAddType === "file" && (
                <div className="w-full flex flex-col items-center mt-2">
                    <button
                        className="btn btn-success w-[160px]"
                        type="button"
                        // onClick={() => confirmExtend()}
                        disabled={
                            !file
                            // loading || apiOkStatuses.includes(Number(msg?.status))
                        }
                    >
                        Add
                        {/* {loading && (
                            <span className="loading loading-spinner loading-sm self-center"></span>
                            )} */}
                    </button>
                </div>
            )}

            <div className="flex justify-center">
                {/* {msg && <Alert msg={msg} />} */}
            </div>
            {/* <div className="flex justify-center mt-6 space-x-4">
                <button
                    className="btn btn-secondary w-4/12"
                    type="button"
                    onClick={() => closeModal()}
                >
                    Close
                </button>
            </div> */}
        </Modal>
    );
};

export default RinexAdd;
