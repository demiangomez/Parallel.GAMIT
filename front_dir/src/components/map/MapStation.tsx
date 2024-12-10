import { useEffect, useRef, useState } from "react";
import {
    MapContainer,
    MapContainerProps,
    Marker,
    Popup,
    TileLayer,
    useMap,
} from "react-leaflet";
import { PopupChildren, Spinner } from "@componentsReact";

import domtoimage from "dom-to-image";
import JSZip from "jszip";
import { LatLngExpression } from "leaflet";
import L from "leaflet";
// @ts-expect-error leaflet omnivore doesnt have any types
import omnivore from "leaflet-omnivore";

import nogapsIcon from "@assets/images/placemark_square.png";
import gapsIcon from "@assets/images/caution.png";

import { StationData } from "@types";

interface MapProps {
    station: StationData | undefined;
    base64Data: string; // Base64 data from the database
    loadPdf: boolean;
    loadedPdfData: boolean;
    setStationLocationScreen?: (url: string) => void;
    setStationLocationDetailScreen?: (url: string) => void;
    setLoadPdf: React.Dispatch<React.SetStateAction<boolean>>;
    setLoadedMap: React.Dispatch<React.SetStateAction<boolean>>;
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

const MapStation = ({
    station,
    base64Data,
    loadPdf,
    loadedPdfData,
    setStationLocationScreen,
    setStationLocationDetailScreen,
    setLoadPdf,
    setLoadedMap,
}: MapProps) => {
    const [mapProps, setMapProps] = useState<MapContainerProps>({
        center: [0, 0],
        zoom: 10,
        scrollWheelZoom: true,
        id: "leaflet-map",
        zoomAnimation: true,
    });

    const [isMapReady, setIsMapReady] = useState(false);
    const MapEvents = ({
        setIsMapReady,
    }: {
        setIsMapReady: (ready: boolean) => void;
    }) => {
        const map = useMap();
        const tilesLoading = new Set<string>(); // Usamos un Set para rastrear los tiles en carga.

        useEffect(() => {
            const handleTileLoadStart = (e: any) => {
                tilesLoading.add(e.tile.src); // Agregar la URL del tile en carga.
                setIsMapReady(false); // Mapa no está listo mientras haya tiles en carga.
            };

            const handleTileLoad = (e: any) => {
                tilesLoading.delete(e.tile.src); // Eliminar el tile cargado del Set.

                if (tilesLoading.size === 0) {
                    setIsMapReady(true); // Marca el mapa como listo.
                }
            };

            const handleZoomStart = () => {
                setIsMapReady(false); // Reinicia el estado al cambiar el nivel de zoom.
                tilesLoading.clear(); // Limpia el contador durante el zoom.
            };

            // Añadir listeners a los TileLayers
            map.eachLayer((layer) => {
                if (layer instanceof L.TileLayer) {
                    layer.on("tileloadstart", handleTileLoadStart);
                    layer.on("tileload", handleTileLoad);
                }
            });

            map.on("zoomstart", handleZoomStart);

            return () => {
                // Quitar listeners al desmontar
                map.eachLayer((layer) => {
                    if (layer instanceof L.TileLayer) {
                        layer.off("tileloadstart", handleTileLoadStart);
                        layer.off("tileload", handleTileLoad);
                    }
                });
                map.off("zoomstart", handleZoomStart);
            };
        }, [map, setIsMapReady]);

        return null;
    };

    useEffect(() => {
        const map = mapRef.current;
        const zoom = map?.getZoom();
        if (isMapReady && loadPdf) {
            if (zoom && zoom === 6) {
                captureImage(1000, (dataUrl) => {
                    setStationLocationScreen &&
                        setStationLocationScreen(dataUrl);
                });
            }
            if (zoom && zoom === 16) {
                captureImage(4000, (dataUrl) => {
                    setStationLocationDetailScreen &&
                        setStationLocationDetailScreen(dataUrl);
                });
            }
        }
    }, [isMapReady, loadPdf]);

    const mapRef = useRef<L.Map | null>(null);

    useEffect(() => {
        const map = mapRef.current;
        if (!map) return;

        map.on("load", () => {
            setIsMapReady(true);
        });

        return () => {
            map.off("load");
        };
    }, [mapRef]);

    const captureImage = (
        timeout: number,
        callback: (dataUrl: string) => void,
    ) => {
        if (!mapRef.current) return;

        setTimeout(() => {
            const container = mapRef?.current?.getContainer();
            if (container) {
                domtoimage
                    .toPng(container, {
                        width: container.clientWidth,
                        height: container.clientHeight,
                    })
                    .then((dataUrl) => {
                        callback(dataUrl);
                    })
                    .catch((error) => {
                        console.error("Error capturing map image:", error);
                    });
            }
        }, timeout);
    };

    useEffect(() => {
        if (mapRef.current && loadPdf) {
            setLoadedMap(false);

            setTimeout(() => {
                setMapProps((prevProps) => ({
                    ...prevProps,
                    center: [station?.lat ?? 0, station?.lon ?? 0],
                    zoom: 6,
                }));
            }, 50);

            setTimeout(() => {
                setMapProps((prevProps) => ({
                    ...prevProps,
                    center: [station?.lat ?? 0, station?.lon ?? 0],
                    zoom: 16,
                }));
            }, 6000);

            setTimeout(() => {
                setMapProps((prevProps) => ({
                    ...prevProps,
                    zoom: 10,
                }));
                setLoadPdf(false);
                setLoadedMap(true);
            }, 15000);
        }
    }, [station, mapRef, loadPdf]);

    const okIcon = new L.Icon({
        iconUrl: nogapsIcon,
        iconSize: [20, 20],
        className: "bg-green-600 border border-black",
    });

    const alertIcon = new L.Icon({
        iconUrl: gapsIcon,
        iconSize: [20, 20],
    });

    useEffect(() => {
        const pos: LatLngExpression = station
            ? [station?.lat ?? 0, station?.lon ?? 0]
            : [0, 0];

        setMapProps((prevProps) => ({
            ...prevProps,
            center: pos,
        }));
    }, [station]);

    const [forceRerender, setForceRerender] = useState(0);

    useEffect(() => {
        setForceRerender((prev) => prev + 1);
    }, [base64Data]);

    const iconGaps =
        station?.has_gaps || !station?.has_stationinfo ? alertIcon : okIcon;

    return (
        <div className="z-10 pt-6 w-6/12 flex justify-center">
            {loadedPdfData === false && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[10000]">
                    <div className=" flex flex-col w-[400px] items-center card card-bordered bg-base-200 p-6 ">
                        <span className="card-title border-b-2 text-xl mb-4">
                            Loading data, please wait...
                        </span>
                        <div className="card-body">
                            <Spinner size={"lg"} />
                        </div>
                    </div>
                </div>
            )}
            <MapContainer
                {...mapProps}
                key={forceRerender}
                className="w-[55vw] h-[55vh] xl:w-[40vw] lg:w-[30vw] md:w-[30vw] sm:w-[20vw]"
                ref={mapRef}
            >
                <MapEvents setIsMapReady={setIsMapReady} />
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    minZoom={4}
                />
                <ChangeView
                    center={mapProps.center ?? [0, 0]}
                    zoom={mapProps.zoom ?? 6}
                />
                <LoadKmzFromBase64 base64Data={base64Data} />
                <Marker
                    ref={(ref) => {
                        setTimeout(() => ref?.openPopup(), 500);
                    }}
                    icon={iconGaps}
                    key={station ? station.lat + station.lon : "key"}
                    position={mapProps.center ?? [0, 0]}
                >
                    {!loadPdf && (
                        <Popup maxWidth={600} minWidth={400}>
                            <PopupChildren station={station} />
                        </Popup>
                    )}
                </Marker>
            </MapContainer>
        </div>
    );
};

export default MapStation;
