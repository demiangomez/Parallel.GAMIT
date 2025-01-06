import { EditControl } from "react-leaflet-draw";
import React, { useEffect, useState } from "react";
import { Modal } from "@componentsReact";

import { MapContainer, TileLayer, FeatureGroup, useMap } from "react-leaflet";
import { LatLngExpression, latLng } from "leaflet";

import { useLocalStorage } from "@hooks";

import { EarthQuakeFormState, MyMapContainerProps } from "@types";

interface MapModalProps {
    formState: EarthQuakeFormState;
    setShowMapModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
    setFormState: React.Dispatch<React.SetStateAction<EarthQuakeFormState>>;
}

const ChangeView = ({
    center,
    zoom,
}: {
    center: LatLngExpression;
    zoom: number;
}) => {
    const map = useMap();

    useEffect(() => {
        map.setView(center, zoom);
    }, [center, zoom, map]);

    return null;
};

// const SetGeo = ({ polygon }: { polygon: any }) => {
//     const map = useMap();

//     useEffect(() => {
//         if (polygon) {
//             const layer = geoJSON(polygon);
//             layer.addTo(map);
//             map.fitBounds(layer.getBounds());
//         }
//     }, [polygon]);

//     return null;
// };

const SetView = () => {
    const map = useMap();

    //-----------------------------------------------------UseLocalStorage-----------------------------------------------------

    const [, setLastZoomLevel] = useLocalStorage("lastZoomLevel", "8");

    const [, setLastPosition] = useLocalStorage("lastPosition", "[0,0]");

    //-----------------------------------------------------UseEffect-----------------------------------------------------

    useEffect(() => {
        const onZoomEnd = () => {
            const currentZoom = map.getZoom();
            setLastZoomLevel(currentZoom.toString());
        };

        const onMoveEnd = () => {
            const currentCenter = map.getCenter();
            setLastPosition([currentCenter.lat, currentCenter.lng].toString());
        };

        map.on("zoomend", onZoomEnd);
        map.on("moveend", onMoveEnd);

        return () => {
            map.off("zoomend", onZoomEnd);
            map.off("moveend", onMoveEnd);
        };
    }, [map]);
    return null;
};

const MapModal = ({
    formState,
    setShowMapModal,
    setFormState,
}: MapModalProps) => {
    //-----------------------------------------------------Constantes-----------------------------------------------------

    //-----------------------------------------------------Funciones-----------------------------------------------------

    const handleCloseModal = () => {};

    const findLimits = (coordinates: any) => {
        const longitudes = coordinates.map((coordinate: any) => coordinate[1]);

        const latitudes = coordinates.map((coordinate: any) => coordinate[0]);

        const max_longitude = Math.max(...longitudes);

        const min_longitude = Math.min(...longitudes);

        const max_latitude = Math.max(...latitudes);

        const min_latitude = Math.min(...latitudes);

        return {
            max_longitude,
            min_longitude,
            max_latitude,
            min_latitude,
        };
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
                ...formState,
                max_latitude: limits.max_latitude.toString(),
                min_latitude: limits.min_latitude.toString(),
                max_longitude: limits.max_longitude.toString(),
                min_longitude: limits.min_longitude.toString(),
                polygon_coordinates: completedCoordinates,
            }),
        );

        setShowMapModal(() => ({ type: "edit", show: false, title: "" }));
    };

    //-----------------------------------------------------UseState------------------------------------------------------

    const [mapProps, setMapProps] = useState<MyMapContainerProps>({
        center: [0, 0],
        zoom: 4,
        scrollWheelZoom: true,
    });

    //-----------------------------------------------------UseEffect-----------------------------------------------------

    useEffect(() => {
        const savedZoomLevel = localStorage.getItem("lastZoomLevel");

        const savedPosition = localStorage.getItem("lastPosition");

        const finalPosition = savedPosition
            ?.split(",")
            .map((pos) => parseFloat(pos));

        let pos: LatLngExpression = [0, 0];
        if (finalPosition && finalPosition.length === 2) {
            pos = latLng(finalPosition[0], finalPosition[1]);
        }

        setMapProps((prevProps) => ({
            ...prevProps,
            zoom: savedZoomLevel ? parseInt(savedZoomLevel) : 4,
            center: pos,
        }));
    }, []);

    return (
        <Modal
            close={true}
            modalId="map"
            size="md"
            handleCloseModal={handleCloseModal}
            setModalState={setShowMapModal}
        >
            <div className="flex flex-col justify-center items-center gap-y-4">
                <h1 className="font-bold">SELECT COORDINATES</h1>
                <MapContainer
                    {...mapProps}
                    preferCanvas={true}
                    zoomControl={false}
                    maxBoundsViscosity={1.0}
                    worldCopyJump={true}
                    className="w-[1000px] h-[600px]"
                >
                    <ChangeView center={mapProps.center} zoom={mapProps.zoom} />
                    <SetView />
                    <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        minZoom={4}
                    />
                    <FeatureGroup>
                        <EditControl
                            position="topright"
                            onCreated={(e) => {
                                handleDrawPolygon(e);
                            }}
                            draw={{
                                rectangle: false,
                                polyline: false,
                                circle: false,
                                marker: false,
                                circlemarker: false,
                                polygon: true,
                            }}
                        />
                    </FeatureGroup>
                </MapContainer>
            </div>
        </Modal>
    );
};

export default MapModal;
