import { useEffect, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import JSZip from "jszip";
import { LatLngExpression } from "leaflet";
import L from "leaflet";
// @ts-expect-error leaflet omnivore doesnt have any types
import omnivore from "leaflet-omnivore";

import { PopupChildren } from "@componentsReact";

import { StationData } from "@types";

interface MyMapContainerProps {
    center: LatLngExpression;
    zoom: number;
    scrollWheelZoom: boolean;
    style?: React.CSSProperties;
}

interface MapProps {
    station: StationData | undefined;
    base64Data: string; // Base64 data from the database
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

const LoadKmzFromBase64 = ({ base64Data }: { base64Data: string }) => {
    const map = useMap();

    useEffect(() => {
        const loadKmzOrKmlFile = async () => {
            if (!base64Data) return;

            try {
                const binaryString = atob(base64Data);
                const len = binaryString.length;
                const bytes = new Uint8Array(len);
                for (let i = 0; i < len; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }
                const arrayBuffer = bytes.buffer;

                // Intentar cargar como KMZ
                try {
                    const zip = await JSZip.loadAsync(arrayBuffer);
                    const kmlFile = zip.file(/.*\.kml/)[0];
                    if (kmlFile) {
                        const kmlString = await kmlFile.async("string");
                        const overlayLayer = omnivore.kml.parse(kmlString);
                        overlayLayer.options = { interactive: false };
                        overlayLayer.addTo(map);
                    } else {
                        console.error("No KML file found in the KMZ archive.");
                    }
                } catch (kmzError) {
                    // Si falla, intentar cargar como KML
                    try {
                        const kmlString = new TextDecoder().decode(arrayBuffer);
                        const overlayLayer = omnivore.kml.parse(kmlString);
                        overlayLayer.options = { interactive: false };
                        overlayLayer.addTo(map);
                    } catch (kmlError) {
                        console.error("Error loading KML file:", kmlError);
                    }
                }
            } catch (error) {
                console.error("Error processing file:", error);
            }
        };

        loadKmzOrKmlFile();
    }, [base64Data, map]);

    return null;
};

const MapStation = ({ station, base64Data }: MapProps) => {
    const [mapProps, setMapProps] = useState<MyMapContainerProps>({
        center: [0, 0],
        zoom: 13,
        scrollWheelZoom: true,
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
        const pos: LatLngExpression = station
            ? [station.lat, station.lon]
            : [0, 0];

        setMapProps((prevProps) => ({
            ...prevProps,
            center: pos,
        }));
    }, [station]);

    const iconGaps =
        station?.has_gaps || !station?.has_stationinfo ? alertIcon : okIcon;

    return (
        <div className="z-10 pt-6 w-6/12 flex justify-center">
            <MapContainer
                {...mapProps}
                className="w-[55vw] h-[55vh] xl:w-[40vw] lg:w-[30vw] md:w-[30vw] sm:w-[20vw]"
            >
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    minZoom={4}
                />
                <ChangeView center={mapProps.center} zoom={mapProps.zoom} />
                <LoadKmzFromBase64 base64Data={base64Data} />
                <Marker
                    icon={iconGaps}
                    key={station ? station.lat + station.lon : "key"}
                    position={mapProps.center}
                >
                    <Popup maxWidth={1000} minWidth={200}>
                        <PopupChildren station={station} />
                    </Popup>
                </Marker>
            </MapContainer>
        </div>
    );
};

export default MapStation;
