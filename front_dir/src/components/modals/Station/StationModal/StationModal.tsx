import { useEffect, useState } from "react";

import { Modal, AddStationByFile, AddStationManual } from "@componentsReact";

import { useFormReducer } from "@hooks";

import { METADATA_STATE } from "@utils/reducerFormStates";

import { Errors } from "@types";
import { useLocation } from "react-router-dom";

interface Props {
    handleCloseModal: () => void;
    setModals: (
        value: React.SetStateAction<
            | {
                  show: boolean;
                  title: string;
                  type: "add" | "edit" | "none";
              }
            | undefined
        >,
    ) => void;
}

const StationModal = ({ handleCloseModal, setModals }: Props) => {
    const [currentPage, setCurrentPage] = useState<number>(1);

    const [showMenu, setShowMenu] = useState<
        { type: string; show: boolean } | undefined
    >(undefined);

    const { formState, dispatch, clearForm } = useFormReducer(METADATA_STATE);

    useEffect(() => {
        dispatch({
            type: "set",
            payload: METADATA_STATE,
        });
    }, []);

    const [addType, setAddType] = useState<"by file" | "manual" | undefined>(
        "manual",
    );

    useEffect(() => {
        dispatch({
            type: "set",
            payload: METADATA_STATE,
        });
    }, []);

    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [coordinatesType, setCoordinatesType] = useState<
        "ecef" | "latlon" | "map" | undefined
    >(undefined);

    useEffect(() => {
        setAddType("manual");
    }, []);

    const internalHandleCloseModal = () => {
        clearForm();
        setMsg(undefined);
        setCoordinatesType(undefined);
        setShowMenu(undefined);
        setModals(undefined);
    };

    const handleCancel = () => {
        if (currentPage === 1) {
            handleCloseModal();
        } else if (currentPage !== 1) {
            setCurrentPage(currentPage - 1);
        }
    };

    const location = useLocation();

    return (
        <Modal
            close={false}
            modalId={"station"}
            size={addType !== "manual" ? "fit" : "xl"}
            handleCloseModal={() => {
                internalHandleCloseModal();
                if (msg?.status === 201 && location.pathname === "/") {
                    handleCloseModal();
                }
            }}
        >
            <div
                className={`flex flex-col items-center justify-center gap-4 ${addType === "manual" ? "h-full" : "h-fit"}`}
            >
                <h1 className="text-2xl font-bold">Add Station</h1>
                {addType === undefined && (
                    <div className="flex flex-row items-center justify-center gap-6">
                        <button
                            className="btn btn-lg btn-active btn-neutral"
                            onClick={() => {
                                setAddType("by file");
                                setCurrentPage(1);
                            }}
                        >
                            Add By File
                        </button>
                        <button
                            className="btn btn-lg btn-active btn-neutral"
                            onClick={() => {
                                setAddType("manual");
                                setCurrentPage(1);
                            }}
                        >
                            Add Manual
                        </button>
                    </div>
                )}
                {addType === "by file" && (
                    <AddStationByFile handleCancel={handleCancel} />
                )}
                {addType === "manual" && (
                    <AddStationManual
                        coordinatesType={coordinatesType}
                        setCoordinatesType={setCoordinatesType}
                        formState={formState as typeof METADATA_STATE}
                        dispatch={dispatch}
                        currentPage={currentPage}
                        msg={msg}
                        setMsg={setMsg}
                        showMenu={showMenu}
                        setShowMenu={setShowMenu}
                    />
                )}
            </div>
        </Modal>
    );
};

export default StationModal;
