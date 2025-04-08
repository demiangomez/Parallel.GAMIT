import React, { useEffect, useState } from "react";
import { Modal, MapModal } from "@componentsReact";
import { showModal, findLimits } from "@utils";
import { EarthQuakeFormState } from "@types";
import { LatLngExpression } from "leaflet";

interface EarthQuakeModalProps {
    formstate: EarthQuakeFormState;
    handleEarthquakes: () => void;
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
    setPosToFly: React.Dispatch<
        React.SetStateAction<LatLngExpression | undefined>
    >;
}

type EarthQuakeFormStateKeys = Omit<EarthQuakeFormState, "polygon_coordinates">;

const EarthQuakeFormModal = ({
    formstate,
    handleEarthquakes,
    setFormState,
    setPosToFly,
    setInitialCenter,
    setShowEarthquakeModal,
    setShowEarthQuakesList,
}: EarthQuakeModalProps) => {
    //---------------------------------------------------------Constantes-------------------------------------------------------------

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

    //---------------------------------------------------------Funciones-------------------------------------------------------------
    const getLocalStorageFilters = () => {
        return JSON.parse(localStorage.getItem("earthQuakeFilters") ?? "{}");
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;

        setFormState((prev) => ({
            ...prev,
            [name]:
                name === "date_start"
                    ? value + "T00:00:00"
                    : name === "date_end"
                      ? value + "T23:59:59"
                      : value,
        }));

        localStorage.setItem(
            "earthQuakeFilters",
            JSON.stringify({
                ...formstate,
                [name]:
                    name === "date_start"
                        ? value + "T00:00:00"
                        : name === "date_end"
                          ? value + "T23:59:59"
                          : value,
            }),
        );
    };

    const handleClenFilters = () => {
        setFormState(initialState);
        localStorage.setItem("earthQuakeFilters", JSON.stringify(initialState));
    };

    const isEmptyForm = (form: EarthQuakeFormState) => {
        if (
            form.id === "" &&
            form.min_magnitude === "" &&
            form.max_magnitude === "" &&
            form.min_depth === "" &&
            form.max_depth === "" &&
            form.min_latitude === "" &&
            form.max_latitude === "" &&
            form.min_longitude === "" &&
            form.max_longitude === "" &&
            form.date_start === undefined &&
            form.date_end === undefined
        )
            return true;
    };

    const handleSubmitForm = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setInitialCenter && setInitialCenter(undefined);

        setShowEarthquakeModal(() => ({
            type: "edit",
            title: "",
            show: false,
        }));

        if (isEmptyForm(formstate)) {
            localStorage.setItem(
                "earthQuakeFilters",
                JSON.stringify(initialState),
            );
        }

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

    const handleDrawPolygon = (e: any) => {
            const latlngs = e.layer.getLatLngs();
            const coordinates = latlngs[0].map((latlng: any) => [
                latlng.lat,
                latlng.lng,
            ]);
            const completedCoordinates = coordinates.concat([coordinates[0]]);
            const limits = findLimits(coordinates);
    
            setFormState((prev) => ({
                ...prev,
                max_latitude: limits.max_latitude.toString(),
                min_latitude: limits.min_latitude.toString(),
                max_longitude: limits.max_longitude.toString(),
                min_longitude: limits.min_longitude.toString(),
                polygon_coordinates: completedCoordinates,
            }));
    
            localStorage.setItem(
                "earthQuakeFilters",
                JSON.stringify({
                    ...formstate,
                    max_latitude: limits.max_latitude.toString(),
                    min_latitude: limits.min_latitude.toString(),
                    max_longitude: limits.max_longitude.toString(),
                    min_longitude: limits.min_longitude.toString(),
                    polygon_coordinates: completedCoordinates,
                }),
            );
    
            setShowMapModal(() => ({ type: "edit", show: false, title: "" }));
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

    //---------------------------------------------------------Return------------------------------------------------

    return (
        <Modal
            modalId="earthquake"
            size="md"
            close={false}
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
                                    type="date"
                                    value={
                                        formstate.date_start?.split("T")[0] ??
                                        ""
                                    }
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
                                    type="date"
                                    value={
                                        formstate.date_end?.split("T")[0] ?? ""
                                    }
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
                    setShowMapModal={setShowMapModal}
                    handleDrawPolygon={handleDrawPolygon}
                    markerType="polygon"
                />
            ) : null}
        </Modal>
    );
};
export default EarthQuakeFormModal;
