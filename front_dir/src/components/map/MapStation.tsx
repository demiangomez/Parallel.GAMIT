import { useEffect, useState, useRef, useCallback } from "react";
import { useApi, useAuth } from "@hooks";
import L, { LatLngExpression } from "leaflet";
import {
    MapContainer,
    MapContainerProps,
    Marker,
    Popup,
    TileLayer,
    useMap,
    ZoomControl,
} from "react-leaflet";

import { PopupChildren, Spinner, VisitsScroller } from "@componentsReact";
import MarkerClusterGroup from "react-leaflet-markercluster";

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
import {
    getStationTypesService,
    getStationStatusService,
    getNearbyStations,
} from "@services";

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

// Helper Components
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

    useEffect(() => {
        const loadKmzOrKmlFile = async () => {
            try {
                const binaryString = atob(base64Data);
                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
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
                        pointToLayer: (_, latlng) =>
                            L.circleMarker(latlng, { radius: 0, opacity: 0 }),
                        style: (feature) => ({
                            color: feature?.properties?.stroke || color,
                            opacity: feature?.properties?.["stroke-opacity"],
                            fillColor: feature?.properties?.["fill-color"],
                        }),
                        onEachFeature: (feature, layer) => {
                            if (feature.properties?.description) {
                                layer.bindPopup(feature.properties.description);
                            }
                        },
                    });

                    if (geoJsonLayer.getBounds().isValid()) {
                        map.fitBounds(geoJsonLayer.getBounds());
                        geoJsonLayer.setStyle({ color });
                        geoJsonLayer.addTo(map);
                    }
                };

                try {
                    // Try as KMZ
                    const zip = await JSZip.loadAsync(arrayBuffer);
                    const kmlFile = zip.file(/.*\.kml/)[0];
                    if (kmlFile) {
                        parseAndAddGeoJSON(await kmlFile.async("string"));
                    }
                } catch {
                    // Try as KML
                    parseAndAddGeoJSON(new TextDecoder().decode(arrayBuffer));
                }
            } catch (error) {
                console.error("Error loading KMZ/KML:", error);
            }
        };

        loadKmzOrKmlFile();
    }, [base64Data, color, map]);

    return null;
};

const MapEvents = ({
    setIsMapReady,
}: {
    setIsMapReady: (ready: boolean) => void;
}) => {
    const map = useMap();
    const tilesLoading = useRef(new Set<string>());

    useEffect(() => {
        const handleTileEvent = (e: any, isLoadStart: boolean) => {
            if (isLoadStart) {
                tilesLoading.current.add(e.tile.src);
                setIsMapReady(false);
            } else {
                tilesLoading.current.delete(e.tile.src);
                if (tilesLoading.current.size === 0) {
                    setIsMapReady(true);
                }
            }
        };

        const handleZoomStart = () => {
            setIsMapReady(false);
            tilesLoading.current.clear();
        };

        map.eachLayer((layer) => {
            if (layer instanceof L.TileLayer) {
                layer.on("tileloadstart", (e) => handleTileEvent(e, true));
                layer.on("tileload", (e) => handleTileEvent(e, false));
            }
        });

        map.on("zoomstart", handleZoomStart);

        return () => {
            map.eachLayer((layer) => {
                if (layer instanceof L.TileLayer) {
                    layer.off("tileloadstart");
                    layer.off("tileload");
                }
            });
            map.off("zoomstart");
        };
    }, [map, setIsMapReady]);

    return null;
};

const NearbyStationsControl = ({
    showNearbyStations,
    nearbyRadius,
    setShowNearbyStations,
    setNearbyRadius,
}: {
    showNearbyStations: boolean;
    nearbyRadius: number;
    setShowNearbyStations: React.Dispatch<React.SetStateAction<boolean>>;
    setNearbyRadius: React.Dispatch<React.SetStateAction<number>>;
}) => {
    const map = useMap();

    return (
        <div className="leaflet-top leaflet-left" style={{ zIndex: 1000 }}>
            <div className="leaflet-control leaflet-bar bg-white p-3 rounded-md shadow-lg mt-2.5 ml-2.5 min-w-[240px]">
                <div className="flex items-center gap-2 mb-3">
                    <input
                        type="checkbox"
                        id="nearby-stations-checkbox"
                        checked={showNearbyStations}
                        onChange={(e) =>
                            setShowNearbyStations(e.target.checked)
                        }
                        className="checkbox checkbox-sm"
                    />
                    <label
                        htmlFor="nearby-stations-checkbox"
                        className="text-sm font-semibold cursor-pointer text-gray-700 select-none"
                    >
                        Show Nearby Stations
                    </label>
                </div>

                {showNearbyStations && (
                    <div
                        className="space-y-2"
                        onMouseEnter={() => {
                            map?.dragging.disable();
                            map?.scrollWheelZoom.disable();
                        }}
                        onMouseLeave={() => {
                            map?.dragging.enable();
                            map?.scrollWheelZoom.enable();
                        }}
                    >
                        <label className="block text-sm font-medium text-gray-700">
                            Radius: {nearbyRadius} km
                        </label>
                        <input
                            type="range"
                            className="range range-xs range-neutral w-full"
                            value={nearbyRadius}
                            onChange={(e) =>
                                setNearbyRadius(parseInt(e.target.value))
                            }
                            step="10"
                            min="100"
                            max="200"
                        />
                    </div>
                )}
            </div>
        </div>
    );
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
    // Hooks
    const { token, logout, user } = useAuth();
    const api = useApi(token, logout);

    // State
    const [isMapReady, setIsMapReady] = useState(false);
    const [zoom6Captured, setZoom6Captured] = useState(false);
    const [zoom16Captured, setZoom16Captured] = useState(false);
    const [showNearbyStations, setShowNearbyStations] = useState(false);
    const [nearbyRadius, setNearbyRadius] = useState(100);
    const [nearbyStations, setNearbyStations] = useState<StationData[]>([]);
    const [overlappedNearbyStations, setOverlappedNearbyStations] = useState<
        StationData[]
    >([]);
    const [overlappedNearbyClusters, setOverlappedNearbyClusters] = useState<
        StationData[][]
    >([]);
    const [mapProps, setMapProps] = useState<MapContainerProps>({
        center: [0, 0],
        zoom: 10,
        scrollWheelZoom: true,
        id: "leaflet-map",
        zoomAnimation: true,
        minZoom: 2,
    });
    const [forceRerender, setForceRerender] = useState(0);
    const [showScroller, setShowScroller] = useState(false);
    const [types, setTypes] = useState<{ image: string; name: string }[]>([]);
    const [statuses, setStatuses] = useState<{ name: string; color: string }[]>(
        [],
    );

    // Refs
    const mapRef = useRef<L.Map | null>(null);
    const markerRef = useRef<L.Marker | null>(null);

    // Helper Functions
    const getColor = useCallback(
        (visit: StationVisitsData) => {
            const visitColor = visitScrollerProps.changeKml.find(
                (visitBool) => visitBool.visitId === visit.id,
            );
            return visitColor?.color || "black";
        },
        [visitScrollerProps.changeKml],
    );

    const captureImage = useCallback(
        (timeout: number, callback: (dataUrl: string) => void) => {
            setTimeout(() => {
                const container = mapRef.current?.getContainer();
                if (container) {
                    domtoimage
                        .toJpeg(container, {
                            width: container.clientWidth,
                            height: container.clientHeight,
                        })
                        .then(callback)
                        .catch(console.error);
                }
            }, timeout);
        },
        [],
    );

    const areStationsOverlapped = useCallback(
        (stationA: StationData, stationB: StationData) => {
            if (
                !mapRef.current ||
                !stationA?.lat ||
                !stationA?.lon ||
                !stationB?.lat ||
                !stationB?.lon
            ) {
                return false;
            }

            const zoom = 16;
            const center = mapRef.current.getCenter();
            const latitude = center.lat;
            const metersPerPixel =
                (156543.03392 * Math.cos((latitude * Math.PI) / 180)) /
                Math.pow(2, zoom);
            const scale = metersPerPixel * 96 * 39.37;
            const VISUAL_ACUITY_MM = 3;
            const minDistanceMeters =
                Number(user?.clustering_distance) >= 0
                    ? Number(user?.clustering_distance)
                    : (VISUAL_ACUITY_MM / 1000) * scale;

            const distance = mapRef.current.distance(
                [stationA.lat, stationA.lon],
                [stationB.lat, stationB.lon],
            );

            return distance < minDistanceMeters;
        },
        [],
    );

    const findOverlappedNearbyStations = useCallback(() => {
        if (!nearbyStations || nearbyStations.length === 0) return;

        const overlappingPairs: StationData[] = [];
        for (let i = 0; i < nearbyStations.length; i++) {
            for (let j = i + 1; j < nearbyStations.length; j++) {
                if (
                    areStationsOverlapped(nearbyStations[i], nearbyStations[j])
                ) {
                    overlappingPairs.push(nearbyStations[i], nearbyStations[j]);
                }
            }
        }
        setOverlappedNearbyStations(
            overlappingPairs.length > 0 ? overlappingPairs : [],
        );
    }, [nearbyStations, areStationsOverlapped]);

    const createNearbyClusters = useCallback(() => {
        if (!overlappedNearbyStations || overlappedNearbyStations.length === 0)
            return;

        const clusters: StationData[][] = [];
        const processed = new Set<number>();

        for (let i = 0; i < overlappedNearbyStations.length; i++) {
            if (processed.has(i)) continue;

            const cluster: StationData[] = [overlappedNearbyStations[i]];
            processed.add(i);

            for (let j = i + 1; j < overlappedNearbyStations.length; j++) {
                if (processed.has(j)) continue;
                if (
                    areStationsOverlapped(
                        overlappedNearbyStations[i],
                        overlappedNearbyStations[j],
                    )
                ) {
                    cluster.push(overlappedNearbyStations[j]);
                    processed.add(j);
                }
            }

            if (cluster.length > 1) {
                clusters.push(cluster);
            }
        }

        setOverlappedNearbyClusters(clusters);
    }, [overlappedNearbyStations, areStationsOverlapped]);

    const fetchNearbyStations = useCallback(async () => {
        if (!station || !showNearbyStations) {
            setNearbyStations([]);
            return;
        }

        try {
            const response = (await getNearbyStations(
                api,
                station.api_id!,
                nearbyRadius,
            )) as { nearby_stations: StationData[] };
            if (response.nearby_stations) {
                setNearbyStations(response.nearby_stations);
            }
        } catch (error) {
            console.error("Error fetching nearby stations:", error);
            setNearbyStations([]);
        }
    }, [api, station, showNearbyStations, nearbyRadius]);

    const getStationStatuses = useCallback(async () => {
        try {
            const res =
                await getStationStatusService<StationStatusServiceData>(api);
            if (res) {
                setStatuses(
                    res.data.map((status: StationStatusData) => ({
                        color: status.color_name,
                        name: status.name,
                    })),
                );
            }
        } catch (err) {
            console.error(err);
        }
    }, [api]);

    const getStationTypes = useCallback(async () => {
        try {
            const res =
                await getStationTypesService<StationTypeServiceData>(api);
            if (res && apiOkStatuses.includes(res.statusCode)) {
                setTypes(
                    res.data.map((type: StationTypeData) => ({
                        image: type.actual_image as string,
                        name: type.name,
                    })),
                );
            }
        } catch (err) {
            console.error(err);
        }
    }, [api]);

    // Cluster icon creators
    const createClusterWithProblem = useCallback(
        (cluster: any) =>
            L.divIcon({
                html: `<span>${cluster.getChildCount()}</span>`,
                className: "custom-marker-cluster-dangerous",
                iconSize: L.point(30, 30, true),
            }),
        [],
    );

    const createClusterWithNoProblem = useCallback(
        (cluster: any) =>
            L.divIcon({
                html: `<span>${cluster.getChildCount()}</span>`,
                className: "custom-marker-cluster-normal",
                iconSize: L.point(30, 30, true),
            }),
        [],
    );

    const anyHasProblems = useCallback(
        (stations: StationData[]) =>
            stations.some((s) => s.has_gaps || !s.has_stationinfo),
        [],
    );

    // Effects
    useEffect(() => {
        if (isMapReady && loadPdf && mapRef.current) {
            const zoom = mapRef.current.getZoom();

            if (zoom === 6 && !zoom6Captured) {
                setZoom6Captured(true);
                captureImage(5000, (dataUrl) => {
                    setStationLocationScreen?.(dataUrl);
                });
            }

            if (zoom === 16 && !zoom16Captured) {
                setZoom16Captured(true);
                captureImage(6000, (dataUrl) => {
                    setStationLocationDetailScreen?.(dataUrl);
                });
            }
        }
    }, [isMapReady, loadPdf, zoom6Captured, zoom16Captured, captureImage]);

    useEffect(() => {
        if (loadPdf) {
            setLoadedMap(false);
            const initialTimeout = setTimeout(() => {
                if (mapRef.current) {
                    setTimeout(() => {
                        setMapProps((prev) => ({
                            ...prev,
                            center: [station?.lat ?? 0, station?.lon ?? 0],
                            zoom: 6,
                            zoomAnimation: false,
                        }));
                    }, 1000);

                    setTimeout(() => {
                        setMapProps((prev) => ({
                            ...prev,
                            center: [station?.lat ?? 0, station?.lon ?? 0],
                            zoom: 16,
                        }));
                    }, 8000);

                    setTimeout(() => {
                        setMapProps((prev) => ({
                            ...prev,
                            zoom: 10,
                            zoomAnimation: true,
                        }));
                        setLoadPdf(false);
                        setLoadedMap(true);
                    }, 17000);
                }
            }, 1000);

            return () => clearTimeout(initialTimeout);
        }
    }, [loadPdf, station, setLoadPdf, setLoadedMap]);

    useEffect(() => {
        setMapProps((prev) => ({
            ...prev,
            center: station ? [station.lat ?? 0, station.lon ?? 0] : [0, 0],
        }));
    }, [station]);

    useEffect(() => {
        setForceRerender((prev) => prev + 1);
    }, [base64Data]);

    useEffect(() => {
        getStationStatuses();
        getStationTypes();
    }, [getStationStatuses, getStationTypes]);

    useEffect(() => {
        fetchNearbyStations();
    }, [showNearbyStations, nearbyRadius, station, fetchNearbyStations]);

    useEffect(() => {
        findOverlappedNearbyStations();
    }, [nearbyStations, findOverlappedNearbyStations, user]);

    useEffect(() => {
        createNearbyClusters();
    }, [overlappedNearbyStations, createNearbyClusters]);

    return (
        <div className="z-10 pt-6 w-6/12 flex justify-center">
            {loadedPdfData === false && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[10000]">
                    <div className="flex flex-col w-[400px] items-center card card-bordered bg-base-200 p-6">
                        <span className="card-title border-b-2 text-xl mb-4">
                            Loading data, please wait...
                        </span>
                        <div className="card-body">
                            <Spinner size="lg" />
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
                minZoom={1}
                zoomControl={false}
            >
                <ZoomControl position="bottomright" />
                <MapEvents setIsMapReady={setIsMapReady} />
                <NearbyStationsControl
                    showNearbyStations={showNearbyStations}
                    nearbyRadius={nearbyRadius}
                    setShowNearbyStations={setShowNearbyStations}
                    setNearbyRadius={setNearbyRadius}
                />

                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    minZoom={1}
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

                {/* Nearby station clusters */}
                {showNearbyStations &&
                    overlappedNearbyClusters.map((cluster, index) => (
                        <MarkerClusterGroup
                            key={`nearby-cluster-${index}`}
                            iconCreateFunction={
                                anyHasProblems(cluster)
                                    ? createClusterWithProblem
                                    : createClusterWithNoProblem
                            }
                        >
                            {cluster.map((nearbyStation) => (
                                <Marker
                                    key={`nearby-${nearbyStation.api_id}`}
                                    position={[
                                        nearbyStation.lat,
                                        nearbyStation.lon,
                                    ]}
                                    icon={chosenIcon(
                                        nearbyStation,
                                        types,
                                        statuses,
                                    )}
                                >
                                    <Popup maxWidth={600} minWidth={400}>
                                        <PopupChildren
                                            station={nearbyStation}
                                        />
                                    </Popup>
                                </Marker>
                            ))}
                        </MarkerClusterGroup>
                    ))}

                {/* Individual nearby stations */}
                {showNearbyStations &&
                    nearbyStations
                        .filter(
                            (ns) =>
                                !overlappedNearbyStations.some(
                                    (ons) => ons.api_id === ns.api_id,
                                ),
                        )
                        .map((nearbyStation) => (
                            <Marker
                                key={`nearby-individual-${nearbyStation.api_id}`}
                                position={[
                                    nearbyStation.lat,
                                    nearbyStation.lon,
                                ]}
                                icon={chosenIcon(
                                    nearbyStation,
                                    types,
                                    statuses,
                                )}
                            >
                                <Popup maxWidth={600} minWidth={400}>
                                    <PopupChildren
                                        station={nearbyStation}
                                        fromMain={true}
                                        reload={true}
                                    />
                                </Popup>
                            </Marker>
                        ))}

                {/* KML/KMZ layers */}
                {base64Data &&
                    (typeof base64Data !== "string" ? (
                        <>
                            {base64Data.visits
                                .filter(
                                    (visit) =>
                                        visit?.navigation_actual_file &&
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
                                ))}
                            {base64Data.stationMeta?.navigation_actual_file &&
                                base64Data.changeMeta && (
                                    <LoadKmzFromBase64
                                        base64Data={
                                            base64Data.stationMeta
                                                .navigation_actual_file ?? ""
                                        }
                                        color="black"
                                    />
                                )}
                        </>
                    ) : (
                        <LoadKmzFromBase64
                            base64Data={base64Data}
                            color="black"
                        />
                    ))}

                {/* Main station marker */}
                <Marker
                    icon={chosenIcon(station as StationData, types, statuses)}
                    key={
                        station
                            ? `${station.lat}-${station.lon}`
                            : "default-marker"
                    }
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
