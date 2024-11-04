import { LatLng, LatLngExpression } from "leaflet";
import L from "leaflet";
import {
    MapContainer,
    Marker,
    Popup,
    TileLayer,
    Tooltip,
    useMap,
} from "react-leaflet";

import { StationData } from "@types";
import { useEffect, useState } from "react";
import PopupChildren from "./PopupChildren";

interface MyMapContainerProps {
    center: LatLngExpression;
    zoom: number;
    scrollWheelZoom: boolean;
    style?: React.CSSProperties;
}

interface MapProps {
    stations: StationData[] | undefined;
    initialCenter: LatLngExpression | undefined;
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

const MapMarkers = ({
    stations,
    initialCenter,
}: {
    stations: StationData[] | undefined;
    initialCenter: LatLngExpression | undefined;
}) => {
    const map = useMap();

    const [markersByBounds, setMarkersByBounds] = useState<
        StationData[] | undefined
    >(undefined);

    map.on("move", () => {
        const mapBounds = map.getBounds();

        const mapEastCorner = mapBounds.getNorthEast();
        const mapWestCorner = mapBounds.getSouthWest();

        setMarkersByBounds(
            stations?.filter(
                (s) =>
                    s?.lat < mapEastCorner?.lat &&
                    s?.lon < mapEastCorner?.lng &&
                    s?.lat > mapWestCorner?.lat &&
                    s?.lon > mapWestCorner?.lng,
            ),
        );
    });

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

    useEffect(() => {
        if (stations && initialCenter) {
            let lat, lng;

            if (initialCenter instanceof LatLng) {
                lat = initialCenter?.lat;
                lng = initialCenter?.lng;
            } else if (Array.isArray(initialCenter)) {
                lat = initialCenter[0];
                lng = initialCenter[1];
            } else {
                lat = initialCenter?.lat;
                lng = initialCenter?.lng;
            }

            map.setView([lat + 1, lng + 1], 4);
        }
    }, [stations]);

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
                                    {s.network_code?.toUpperCase() +
                                        "." +
                                        s.station_code?.toUpperCase()}
                                </strong>
                            </Tooltip>{" "}
                            <Popup maxWidth={600} minWidth={400}>
                                <PopupChildren station={s} fromMain={true} />
                            </Popup>{" "}
                        </Marker>
                    );
                })}
        </>
    );
};

const Map = ({ stations, initialCenter }: MapProps) => {
    const [mapProps, setMapProps] = useState<MyMapContainerProps>({
        center: [0, 0],
        zoom: 4,
        scrollWheelZoom: true,
    });

    useEffect(() => {
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
            zoom: 8,
            center: pos,
        }));
    }, [stations]);

    return (
        <div className="z-10 pt-6 w-full flex justify-center">
            <MapContainer
                {...mapProps}
                preferCanvas={true}
                maxBoundsViscosity={1.0}
                worldCopyJump={true}
                className="w-[80vw] h-[70vh] xl:w-[70vw] lg:w-[60vw] md:w-[50vw] sm:w-[40vw]"
            >
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    minZoom={4}
                />

                {/* <TileLayer
                    url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png"
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                    subdomains="abcd"
                    minZoom={5}
                /> */}
                <ChangeView center={mapProps.center} zoom={mapProps.zoom} />
                <MapMarkers stations={stations} initialCenter={initialCenter} />
            </MapContainer>
        </div>
    );
};

export default Map;
