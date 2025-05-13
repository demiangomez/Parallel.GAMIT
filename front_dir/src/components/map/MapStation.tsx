import { useEffect, useState, useRef } from "react";
import { useApi, useAuth } from "@hooks";
import L, { LatLngExpression } from "leaflet";
import {
    MapContainer,
    MapContainerProps,
    Marker,
    Popup,
    TileLayer,
    useMap,
} from "react-leaflet";

import { PopupChildren, Spinner, VisitsScroller } from "@componentsReact";

import * as toGeoJSON from "@tmcw/togeojson";

import domtoimage from "dom-to-image";
import JSZip from "jszip";
import {
    StationData,
    StationMetadataServiceData,
    StationVisitsData,
    StationTypeServiceData,
    StationStatusServiceData,
    StationTypeData,
    StationStatusData,
} from "@types";

import { apiOkStatuses, chosenIcon } from "@utils";
import { getStationTypesService, getStationStatusService } from "@services";

interface VisitsStates {
    visitId: number;
    checked: boolean;
    color: string;
}

interface VisitScrollerProps {
    visits: StationVisitsData[];
    changeKml: VisitsStates[];
    changeMeta: boolean;
    setChangeKml: React.Dispatch<React.SetStateAction<VisitsStates[]>>;
    setChangeMeta: React.Dispatch<React.SetStateAction<boolean>>;
    stationMeta: StationMetadataServiceData;
}

interface MapProps {
    visitScrollerProps: VisitScrollerProps;
    base64Data:
        | {
              visits: StationVisitsData[];
              stationMeta: StationMetadataServiceData;
              changeKml: VisitsStates[];
              changeMeta: boolean;
          }
        | string
        | undefined;
    loadPdf: boolean;
    loadedPdfData: boolean;
    station: StationData | undefined;
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

const LoadKmzFromBase64 = ({
    base64Data,
    color,
}: {
    base64Data: string;
    color: string;
}) => {
    const map = useMap();

    //--------------------------------------------------Funciones--------------------------------------------------

    //--------------------------------------------------UseEffect--------------------------------------------------
    useEffect(() => {
        const loadKmzOrKmlFile = async () => {
            try {
                const binaryString = atob(base64Data);
                const len = binaryString.length;
                const bytes = new Uint8Array(len);
                for (let i = 0; i < len; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }
                const arrayBuffer = bytes.buffer;

                const parseAndAddGeoJSON = (kmlString: string) => {
                    const dom = new DOMParser().parseFromString(
                        kmlString,
                        "application/xml",
                    );
                    const geojson = toGeoJSON.kml(dom);

                    const geoJsonLayer = L.geoJSON(geojson, {
                        pointToLayer: (feature, latlng) => {
                            if (feature.properties) {
                                return L.circleMarker(latlng, {
                                    radius: 0,
                                    opacity: 0,
                                }); // Return invisible marker instead of null
                            }
                            return L.circleMarker(latlng, {
                                radius: 0,
                                opacity: 0,
                            }); // Return invisible marker instead of null
                        },
                        style: (feature) => {
                            return feature
                                ? {
                                      color: feature.properties.stroke,
                                      opacity:
                                          feature.properties["stroke-opacity"],
                                      fillColor:
                                          feature.properties["fill-color"],
                                      //   fillOpacity:
                                      //       feature.properties["fill-opacity"],
                                  }
                                : {};
                        },
                        onEachFeature: (_feature, layer) => {
                            if (
                                _feature.properties &&
                                _feature.properties.description
                            ) {
                                layer.bindPopup(
                                    _feature.properties.description,
                                );
                            }
                        },
                    });

                    if (geoJsonLayer.getBounds().isValid()) {
                        map.fitBounds(geoJsonLayer.getBounds());
                        // map.zoomOut(1);
                        geoJsonLayer.setStyle({
                            color: color,
                        });
                        geoJsonLayer.addTo(map);
                    }
                };

                try {
                    // Intenta como KMZ
                    const zip = await JSZip.loadAsync(arrayBuffer);
                    const kmlFile = zip.file(/.*\.kml/)[0];

                    if (kmlFile) {
                        const kmlString = await kmlFile.async("string");
                        parseAndAddGeoJSON(kmlString);
                    } else {
                        console.error("No KML file found in KMZ.");
                    }
                } catch (kmzError) {
                    try {
                        // Intenta como KML suelto
                        const kmlString = new TextDecoder().decode(arrayBuffer);
                        parseAndAddGeoJSON(kmlString);
                    } catch (kmlError) {
                        console.error("Error parsing KML:", kmlError);
                    }
                }
            } catch (error) {
                console.error("Error decoding base64 file:", error);
            }
        };

        loadKmzOrKmlFile();
    }, [base64Data, map]);

    return null;
};

const MapStation = ({
    visitScrollerProps,
    base64Data,
    loadPdf,
    loadedPdfData,
    station,
    setStationLocationScreen,
    setStationLocationDetailScreen,
    setLoadPdf,
    setLoadedMap,
}: MapProps) => {
    //---------------------------------------------------------UseAuth-------------------------------------------------------------
    const { token, logout } = useAuth();

    //---------------------------------------------------------UseApi-------------------------------------------------------------
    const api = useApi(token, logout);

    const [isMapReady, setIsMapReady] = useState(false);

    const [zoom6Captured, setZoom6Captured] = useState(false);
    const [zoom16Captured, setZoom16Captured] = useState(false);

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

        if (isMapReady && loadPdf && map) {
            if (zoom === 6 && !zoom6Captured) {
                setZoom6Captured(true);
                // Mayor tiempo de espera para la captura
                captureImage(5000, (dataUrl) => {
                    setStationLocationScreen &&
                        setStationLocationScreen(dataUrl);
                });
            }

            if (zoom === 16 && !zoom16Captured) {
                setZoom16Captured(true);
                // Mayor tiempo de espera para la captura
                captureImage(6000, (dataUrl) => {
                    setStationLocationDetailScreen &&
                        setStationLocationDetailScreen(dataUrl);
                });
            }
        }
    }, [isMapReady, loadPdf]);

    //--------------------------------------------------Funciones--------------------------------------------------

    const getColor = (visit: StationVisitsData) => {
        const visitColor = visitScrollerProps.changeKml.find(
            (visitBool) => visitBool.visitId === visit.id,
        );
        if (visitColor) {
            return visitColor.color;
        }
        return "black";
    };

    const captureImage = (
        timeout: number,
        callback: (dataUrl: string) => void,
    ) => {
        if (!mapRef.current) return;

        setTimeout(() => {
            const container = mapRef?.current?.getContainer();
            if (container) {
                domtoimage
                    .toJpeg(container, {
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

    const getStationStatuses = async () => {
        try {
            const res =
                await getStationStatusService<StationStatusServiceData>(api);
            if (res) {
                const statuses = res.data.map((status: StationStatusData) => {
                    return {
                        color: status.color_name,
                        name: status.name,
                    };
                });
                setStatuses(statuses);
            }
        } catch (err) {
            console.error(err);
        }
    };

    const getStationTypes = async () => {
        try {
            const res =
                await getStationTypesService<StationTypeServiceData>(api);
            if (res && apiOkStatuses.includes(res.statusCode)) {
                const types = res.data.map((type: StationTypeData) => {
                    return {
                        image: type.actual_image as string,
                        name: type.name,
                    };
                });
                setTypes(types);
            }
        } catch (err) {
            console.error(err);
        }
    };

    //--------------------------------------------------UseState--------------------------------------------------

    const [mapProps, setMapProps] = useState<MapContainerProps>({
        center: [0, 0],
        zoom: 10,
        scrollWheelZoom: true,
        id: "leaflet-map",
        zoomAnimation: true,
    });

    const [forceRerender, setForceRerender] = useState(0);

    const [showScroller, setShowScroller] = useState(false);

    const [types, setTypes] = useState<{ image: string; name: string }[]>([]);
    const [statuses, setStatuses] = useState<{ name: string; color: string }[]>(
        [],
    );

    //--------------------------------------------------UseRef--------------------------------------------------

    const mapRef = useRef<L.Map | null>(null);
    const markerRef = useRef<L.Marker | null>(null);

    //--------------------------------------------------UseEffect--------------------------------------------------

    useEffect(() => {
        // Comprueba que loadPdf sea true y espera a que el mapa esté realmente disponible
        if (loadPdf) {
            setLoadedMap(false);

            // Dale tiempo al mapa para inicializarse completamente
            const initialTimeout = setTimeout(() => {
                if (mapRef.current) {
                    // Primer zoom (6) - Espera un poco más para asegurar que el mapa esté listo
                    setTimeout(() => {
                        setMapProps((prevProps) => ({
                            ...prevProps,
                            center: [station?.lat ?? 0, station?.lon ?? 0],
                            zoom: 6,
                            zoomAnimation: false, // Deshabilitar animación durante captura
                        }));
                    }, 1000);

                    // Segundo zoom (16)
                    setTimeout(() => {
                        setMapProps((prevProps) => ({
                            ...prevProps,
                            center: [station?.lat ?? 0, station?.lon ?? 0],
                            zoom: 16,
                        }));
                    }, 8000);

                    setTimeout(() => {
                        setMapProps((prevProps) => ({
                            ...prevProps,
                            zoom: 10,
                            zoomAnimation: true, // Reactivar animación
                        }));
                        setLoadPdf(false);
                        setLoadedMap(true);
                    }, 17000);
                } else {
                    console.warn("Map ref still not available after timeout");
                }
            }, 1000); // Espera 1 segundo para asegurar que el mapa esté montado

            return () => clearTimeout(initialTimeout);
        }
    }, [loadPdf, station]);

    useEffect(() => {
        const pos: LatLngExpression = station
            ? [station?.lat ?? 0, station?.lon ?? 0]
            : [0, 0];

        setMapProps((prevProps) => ({
            ...prevProps,
            center: pos,
        }));
    }, [station]);

    useEffect(() => {
        setForceRerender((prev) => prev + 1);
    }, [base64Data]);

    useEffect(() => {
        getStationStatuses();
        getStationTypes();
    }, []);

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
                style={{ zIndex: 1000 }}
                whenReady={() => {
                    if (forceRerender === 0) {
                        setTimeout(() => {
                            markerRef.current?.openPopup();
                        }, 500);
                    }
                }}
            >
                <MapEvents setIsMapReady={setIsMapReady} />
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    minZoom={4}
                />
                {!loadPdf && (
                    <VisitsScroller
                        map={mapRef.current}
                        showScroller={showScroller}
                        visits={visitScrollerProps.visits}
                        changeKml={visitScrollerProps.changeKml}
                        changeMeta={visitScrollerProps.changeMeta}
                        stationMeta={visitScrollerProps.stationMeta}
                        setChangeKml={visitScrollerProps.setChangeKml}
                        setChangeMeta={visitScrollerProps.setChangeMeta}
                        setShowScroller={setShowScroller}
                    />
                )}

                <ChangeView
                    center={mapProps.center ?? [0, 0]}
                    zoom={mapProps.zoom ?? 9}
                />
                {base64Data &&
                    (typeof base64Data !== "string" &&
                    Array.isArray(base64Data.visits) ? (
                        base64Data.visits
                            .filter(
                                (visit) =>
                                    visit &&
                                    visit.navigation_actual_file &&
                                    base64Data.changeKml.some(
                                        (kml) =>
                                            kml.visitId === visit.id &&
                                            kml.checked,
                                    ),
                            )
                            .map((visit) => (
                                <LoadKmzFromBase64
                                    key={visit.id}
                                    base64Data={
                                        visit.navigation_actual_file ?? ""
                                    }
                                    color={getColor(visit)}
                                />
                            ))
                    ) : (
                        <LoadKmzFromBase64
                            base64Data={
                                typeof base64Data === "string" ? base64Data : ""
                            }
                            color={"black"}
                        />
                    ))}
                {base64Data &&
                typeof base64Data !== "string" &&
                base64Data.stationMeta &&
                base64Data.stationMeta.navigation_actual_file &&
                base64Data.changeMeta ? (
                    <LoadKmzFromBase64
                        base64Data={
                            base64Data.stationMeta.navigation_actual_file ?? ""
                        }
                        color={"black"}
                    />
                ) : null}
                <Marker
                    icon={
                        chosenIcon(station as StationData, types, statuses) &&
                        chosenIcon(station as StationData, types, statuses)
                    }
                    key={station ? station?.lat + station?.lon : "key"}
                    position={mapProps.center ?? [0, 0]}
                    ref={markerRef}
                >
                    {!loadPdf && station && (
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
