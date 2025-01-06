import React, { useEffect, useState } from "react";
import { Modal, MapModal } from "@componentsReact";
import { showModal } from "@utils";
import { EarthQuakeFormState } from "@types";
import { LatLngExpression } from "leaflet";

interface EarthQuakeModalProps {
    formstate: EarthQuakeFormState;
    setInitialCenter?: React.Dispatch<
        React.SetStateAction<LatLngExpression | undefined>
    >;
    setFormState: React.Dispatch<React.SetStateAction<EarthQuakeFormState>>;
    setShowEarthQuakesList: React.Dispatch<React.SetStateAction<boolean>>;
    setShowEarthquakeModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
    handleEarthquakes: () => void;
    setPosToFly: React.Dispatch<
        React.SetStateAction<LatLngExpression | undefined>
    >;
}

type EarthQuakeFormStateKeys = Omit<EarthQuakeFormState, "polygon_coordinates">;

const EarthQuakeFormModal = ({
    formstate,
    setInitialCenter,
    setFormState,
    setShowEarthquakeModal,
    setShowEarthQuakesList,
    handleEarthquakes,
    setPosToFly,
}: EarthQuakeModalProps) => {
    //---------------------------------------------------------Constantes-------------------------------------------------------------

    const formEntries = [
        "id",
        "min_magnitude",
        "max_magnitude",
        "min_depth",
        "max_depth",
        "min_latitude",
        "max_latitude",
        "min_longitude",
        "max_longitude",
    ];

    const getLocalStorageFilters = () => {
        return JSON.parse(localStorage.getItem("earthQuakeFilters") ?? "{}");
    };

    //---------------------------------------------------------Funciones-------------------------------------------------------------

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;

        setFormState((prev) => ({
            ...prev,
            [name]: value,
        }));

        localStorage.setItem(
            "earthQuakeFilters",
            JSON.stringify({
                ...formstate,
                [name]: value,
            }),
        );
    };

    const handleClenFilters = () => {
        const initialState: EarthQuakeFormState = {
            id: "",
            min_magnitude: "",
            max_magnitude: "",
            min_depth: "",
            max_depth: "",
            min_latitude: "",
            max_latitude: "",
            min_longitude: "",
            max_longitude: "",
            date_start: undefined,
            date_end: undefined,
            polygon_coordinates: [[]],
        };

        setFormState(initialState);
        localStorage.setItem("earthQuakeFilters", JSON.stringify(initialState));
    };

    const handleSubmitForm = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setInitialCenter && setInitialCenter(undefined);
        setShowEarthquakeModal(() => ({
            type: "edit",
            title: "",
            show: false,
        }));
        handleEarthquakes();
        setPosToFly(undefined);
        setShowEarthQuakesList(true);
    };

    const divFormEntries = () => {
        const divs = formEntries.slice(1);

        const finalArray = [];

        let subArray = [];

        for (let i = 0; i < divs.length; i++) {
            if (i % 2 === 0) {
                subArray.push(divs[i]);
            } else {
                subArray.push(divs[i]);
                finalArray.push(subArray);
                subArray = [];
            }
        }

        return finalArray;
    };

    //---------------------------------------------------------useState-------------------------------------------------------------

    const [showMapModal, setShowMapModal] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    //---------------------------------------------------------useEffect-------------------------------------------------------------

    useEffect(() => {
        const localStorageFilters = getLocalStorageFilters();
        setFormState((prev) => ({
            ...prev,
            ...localStorageFilters,
        }));
    }, [setFormState]);

    useEffect(() => {
        showMapModal?.show && showModal(showMapModal.title);
    }, [showMapModal]);

    return (
        <Modal
            close={false}
            modalId="earthquake"
            size="md"
            handleCloseModal={() => undefined}
            setModalState={setShowEarthquakeModal}
        >
            <div>
                <form
                    className="form-control space-y-2 mb-2"
                    onSubmit={handleSubmitForm}
                >
                    <div className="flex flex-col w-full space-y-1">
                        <label className="font-bold">
                            {formEntries[0].replace(/_/g, " ").toUpperCase()}
                        </label>
                        <input
                            type="text"
                            name={formEntries[0]}
                            value={formstate.id ?? ""}
                            className="input input-bordered"
                            onChange={(e) => handleChange(e)}
                        />
                    </div>
                    <div className="flex flex-col w-full space-y-1">
                        <label className="font-bold">DATE</label>
                        <div className="join">
                            <label
                                htmlFor="date_start"
                                className="input join-item input-bordered flex items-center w-full"
                            >
                                <input
                                    type="datetime-local"
                                    value={formstate.date_start ?? ""}
                                    name="date_start"
                                    id="date_start"
                                    className="w-full"
                                    onChange={(e) => {
                                        handleChange(e);
                                    }}
                                />
                            </label>
                            <span className="join-item px-6 text-lg place-content-center bg-neutral-content border border-neutral-300">
                                to
                            </span>
                            <label
                                htmlFor="date_end"
                                className="input join-item input-bordered flex items-center w-full"
                            >
                                <input
                                    type="datetime-local"
                                    value={formstate.date_end ?? ""}
                                    name="date_end"
                                    id="date_end"
                                    className="w-full"
                                    onChange={(e) => {
                                        handleChange(e);
                                    }}
                                />
                            </label>
                        </div>
                    </div>
                    {divFormEntries().map((div, divIndex) => {
                        const title = (n: string, i: number) => {
                            return n
                                .replace(/_/g, " ")
                                .toUpperCase()
                                .split(" ")[i];
                        };
                        return (
                            <div key={`div-${divIndex}`}>
                                <div className="flex flex-col w-full space-y-1">
                                    <label className="font-bold">
                                        {title(div[0], 1)}
                                    </label>
                                    <div className="join space-x-4">
                                        {div.map((entry, entryIndex) => {
                                            return (
                                                <React.Fragment
                                                    key={`entry-${entryIndex}`}
                                                >
                                                    <label
                                                        htmlFor={entry}
                                                        className="input join-item input-bordered flex items-center w-full"
                                                    >
                                                        <input
                                                            type="text"
                                                            name={entry}
                                                            id={entry}
                                                            value={
                                                                formstate[
                                                                    entry as keyof EarthQuakeFormStateKeys
                                                                ] ?? ""
                                                            }
                                                            className="w-full"
                                                            placeholder={title(
                                                                entry,
                                                                0,
                                                            )}
                                                            onChange={(e) => {
                                                                handleChange(e);
                                                            }}
                                                        />
                                                    </label>
                                                </React.Fragment>
                                            );
                                        })}
                                    </div>
                                </div>
                            </div>
                        );
                    })}

                    <div className="flex w-full justify-center space-x-4 items-center">
                        <button
                            className="btn btn-success w-[200px] self-center mt-4"
                            type="submit"
                        >
                            Apply parameters
                        </button>
                        <button
                            type="button"
                            className="btn btn-primary w-[200px] self-center mt-4"
                            onClick={() =>
                                setShowMapModal({
                                    show: true,
                                    title: "map",
                                    type: "none",
                                })
                            }
                        >
                            Select Coordinates
                        </button>
                        <a
                            className="link link-hover self-end"
                            onClick={() => handleClenFilters()}
                        >
                            Clean parameters
                        </a>
                    </div>
                </form>
            </div>
            {showMapModal && showMapModal.title === "map" ? (
                <MapModal
                    formState={formstate}
                    setShowMapModal={setShowMapModal}
                    setFormState={setFormState}
                />
            ) : null}
        </Modal>
    );
};
export default EarthQuakeFormModal;
