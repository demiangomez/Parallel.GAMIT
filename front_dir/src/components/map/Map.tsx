import { LatLngExpression } from "leaflet";
import L from "leaflet";
import {
    MapContainer,
    Marker,
    Popup,
    TileLayer,
    Tooltip,
    useMap,
} from "react-leaflet";
import { useEffect, useState } from "react";
import { PopupChildren } from "@componentsReact";

import { useLocalStorage } from "@hooks";

import { GetParams, StationData } from "@types";

interface MyMapContainerProps {
    center: LatLngExpression;
    zoom: number;
    scrollWheelZoom: boolean;
    style?: React.CSSProperties;
}

interface MapProps {
    stations: StationData[] | undefined;
    initialCenter: LatLngExpression | undefined;
    mainParams: GetParams;
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

const MapMarkers = ({ stations, initialCenter, mainParams }: MapProps) => {
    const map = useMap();

    const [lastZoomLevel, setLastZoomLevel] = useLocalStorage(
        "lastZoomLevel",
        "8",
    );

    const [markersByBounds, setMarkersByBounds] = useState<
        StationData[] | undefined
    >(undefined);

    const updateMarkersByBounds = () => {
        const mapBounds = map.getBounds();

        const mapEastCorner = mapBounds.getNorthEast();
        const mapWestCorner = mapBounds.getSouthWest();

        const filteredStations = stations?.filter(
            (s) =>
                s?.lat < mapEastCorner?.lat &&
                s?.lon < mapEastCorner?.lng &&
                s?.lat > mapWestCorner?.lat &&
                s?.lon > mapWestCorner?.lng,
        );

        setMarkersByBounds(filteredStations);
    };

    useEffect(() => {
        // Actualizar marcadores cuando cambia initialCenter
        if (initialCenter) {
            map.setView(
                initialCenter,
                lastZoomLevel ? parseInt(lastZoomLevel) : 8,
            );
            updateMarkersByBounds();
        }
    }, [initialCenter, map]);

    useEffect(() => {
        // Actualizar marcadores cuando el mapa se mueve
        const onMove = () => updateMarkersByBounds();
        map.on("move", onMove);

        return () => {
            map.off("move", onMove);
        };
    }, [stations, map]);

    useEffect(() => {
        const onZoomEnd = () => {
            const currentZoom = map.getZoom();
            setLastZoomLevel(currentZoom.toString());
            localStorage.setItem("lastZoomTime", new Date().toISOString());
        };

        map.on("zoomend", onZoomEnd);

        return () => {
            map.off("zoomend", onZoomEnd);
        };
    }, [map]);

    const southWest = L.latLng(-100.98155760646617, -250);
    const nortEast = L.latLng(100.99346179538875, 250);

    const bounds = L.latLngBounds(southWest, nortEast);

    map.setMaxBounds(bounds);
    map.on("drag", () => {
        map.panInsideBounds(bounds, { animate: false });
    });

    const okIcon = new L.Icon({
        iconUrl:
            "https://maps.google.com/mapfiles/kml/shapes/placemark_square.png",
        iconSize: [20, 20],
        className: "bg-green-600 border border-black",
    });

    const alertIcon = new L.Icon({
        iconUrl: "https://maps.google.com/mapfiles/kml/shapes/caution.png",
        iconSize: [20, 20],
    });

    const stationTooltip = (s: StationData) => {
        return (s.network_code?.toUpperCase() +
            "." +
            s.station_code?.toUpperCase()) as string;
    };

    return (
        <>
            {markersByBounds &&
                markersByBounds?.map((s) => {
                    const iconGaps =
                        s.has_gaps || !s.has_stationinfo ? alertIcon : okIcon;
                    const pos: LatLngExpression = [s?.lat ?? 0, s?.lon ?? 0];
                    return (
                        <Marker
                            icon={iconGaps}
                            key={s?.lat + s?.lon + (s?.api_id ?? 0)}
                            position={pos}
                        >
                            {" "}
                            <Tooltip>
                                <strong className="text-lg">
                                    {stationTooltip(s)}
                                </strong>
                            </Tooltip>{" "}
                            <Popup maxWidth={600} minWidth={400}>
                                <PopupChildren
                                    station={s}
                                    fromMain={true}
                                    mainParams={mainParams}
                                />
                            </Popup>{" "}
                        </Marker>
                    );
                })}
        </>
    );
};

const Map = ({ stations, initialCenter, mainParams }: MapProps) => {
    const [mapProps, setMapProps] = useState<MyMapContainerProps>({
        center: [0, 0],
        zoom: 4,
        scrollWheelZoom: true,
    });

    useEffect(() => {
        const savedZoomTime = localStorage.getItem("lastZoomTime");

        const now = new Date().toISOString();

        const timeDiff =
            new Date(now).getTime() - new Date(savedZoomTime ?? now).getTime();

        if (timeDiff > 1.44e7) {
            localStorage.setItem("lastZoomLevel", "8");
        }

        const savedZoomLevel = localStorage.getItem("lastZoomLevel");

        const pos: LatLngExpression = initialCenter
            ? initialCenter
            : stations && stations.length > 0
              ? ([
                    stations.find((s) => s.lat && s.lon)?.lat,
                    stations.find((s) => s.lat && s.lon)?.lon,
                ] as LatLngExpression)
              : [0, 0];

        setMapProps((prevProps) => ({
            ...prevProps,
            zoom: savedZoomLevel ? parseInt(savedZoomLevel) : 8,
            center: pos,
        }));
    }, []);

    return (
        <div className="z-10 w-full flex justify-center">
            <MapContainer
                {...mapProps}
                preferCanvas={true}
                maxBoundsViscosity={1.0}
                worldCopyJump={true}
                className="w-[100vw] h-[92vh]"
            >
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    minZoom={4}
                />
                <ChangeView center={mapProps.center} zoom={mapProps.zoom} />
                <MapMarkers
                    stations={stations}
                    initialCenter={initialCenter}
                    mainParams={mainParams}
                />
            </MapContainer>
        </div>
    );
};

export default Map;
