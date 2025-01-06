import { LatLngExpression } from "leaflet";
import L from "leaflet";

import {
    MapContainer,
    Marker,
    Popup,
    TileLayer,
    Tooltip,
    useMap,
    ZoomControl,
} from "react-leaflet";
import JSZip from "jszip";
// @ts-expect-error leaflet omnivore doesnt have any types
import omnivore from "leaflet-omnivore";

import { useEffect, useState } from "react";
import { PopupChildren } from "@componentsReact";

import {useLocalStorage } from "@hooks";

import {
    GetParams,
    StationData,
    FilterState,
    EarthquakeData,
    MyMapContainerProps,
    StationsAffectedServiceData,
    StationAffectedInfo,
} from "@types";

import { isStationFiltered, chosenIcon } from "@utils";

interface MapProps {
    stations: StationData[] | undefined;
    initialCenter: LatLngExpression | undefined;
    mainParams: GetParams;
    setMainParams?: React.Dispatch<React.SetStateAction<GetParams>>;
    topoMap?: boolean | undefined;
    filters?: {
        openFilters: boolean;
        stationType: boolean;
        stationWithProblems: boolean;
        stationWithoutProblems: boolean;
        stationStatus: boolean;
    };
    filterState?: FilterState;
    mapState: boolean;
    earthquakes: EarthquakeData[];
    markersByBounds?: StationData[] | EarthquakeData[];
    setMarkersByBounds: React.Dispatch<
        React.SetStateAction<StationData[] | EarthquakeData[] | undefined>
    >;
    earthquakesFiltered: EarthquakeData[];
    setEarthquakesFiltered: React.Dispatch<
        React.SetStateAction<EarthquakeData[]>
    >;
    handleEarthquakeState: (earthquake: EarthquakeData) => void;
    posToFly: LatLngExpression | undefined;
    earthquakeAffectedStations: StationsAffectedServiceData | undefined;
    earthQuakeChosen: EarthquakeData | undefined;
    setForceSyncScrollerMap: React.Dispatch<React.SetStateAction<number>>;
    showEarthquakeList: boolean;
    forceSyncDropLeftMap: number;
}

export const ChangeView = ({
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

    //--------------------------------------------------Funciones--------------------------------------------------

    function removeMarkersFromKml(base64Kml: string): string {
        const decodedXml = atob(base64Kml);

        const parser = new DOMParser();

        const xmlDoc = parser.parseFromString(decodedXml, "application/xml");

        const placemarks = Array.from(xmlDoc.getElementsByTagName("Placemark"));

        placemarks.forEach((placemark) => {
            if (placemark.getElementsByTagName("Point").length > 0) {
                placemark.parentNode?.removeChild(placemark);
            }
        });

        const serializer = new XMLSerializer();

        const updatedXml = serializer.serializeToString(xmlDoc);

        const base64UpdatedXml = btoa(updatedXml);

        return base64UpdatedXml;
    }

    const removeOldKmls = () => {
        map.eachLayer((layer) => {
            // Verifica si es una capa creada por omnivore
            if (!(layer instanceof L.TileLayer)) {
                map.removeLayer(layer);
            }
        });
    };

    //--------------------------------------------------UseEffect--------------------------------------------------

    useEffect(() => {
        const loadKmzOrKmlFile = async () => {
            if (!base64Data) return;

            removeOldKmls();
            try {
                const updatedBase64Data = removeMarkersFromKml(base64Data);
                const binaryString = atob(updatedBase64Data);
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
                        overlayLayer.setStyle({ color: "blue" });
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
                        overlayLayer.setStyle({ color: "blue" });
                        overlayLayer.options = { interactive: false };
                        overlayLayer.addTo(map);
                    } catch (kmlError) {
                        console.error("Error loading KML file:", kmlError);
                    }
                }
            } catch (error) {
                console.error("Error processing file:", error);
            }
            finally{
                const pos = map.getCenter();
                map.setView([pos.lat + 0.001, pos.lng + 0.001]);
            }
        };

        loadKmzOrKmlFile();
    }, [base64Data, map]);

    return null;
};

const MapMarkers = ({
    stations,
    initialCenter,
    mainParams,
    mapState,
    markersByBounds,
    earthquakes,
    earthquakeAffectedStations,
    earthQuakeChosen,
    earthquakesFiltered,
    posToFly,
    filters,
    filterState,
    setMarkersByBounds,
    setEarthquakesFiltered,
    handleEarthquakeState,
    setForceSyncScrollerMap,
    showEarthquakeList,
}: MapProps) => {
    //---------------------------------------------------------------------------Constantes--------------------------------------------------------------------------------------
    const map = useMap();

    const southWest = L.latLng(-100.98155760646617, -250);
    const nortEast = L.latLng(100.99346179538875, 250);

    const bounds = L.latLngBounds(southWest, nortEast);

    map.setMaxBounds(bounds);
    map.on("drag", () => {
        const extendedBounds = bounds.pad(0.5);
        map.panInsideBounds(extendedBounds, { animate: false });
    });

    //---------------------------------------------------------------------------UseLocalStorage--------------------------------------------------------------------------------------
    const [lastZoomLevel, setLastZoomLevel] = useLocalStorage(
        "lastZoomLevel",
        "8",
    );

    const [, setLastPosition] = useLocalStorage("lastPosition", "[0,0]");

    //-------------------------------------------------------------------------------UseMemo--------------------------------------------------------------------------------------

    //-------------------------------------------------------------------------------UseStates--------------------------------------------------------------------------------------

    const [forceRenderMarker, setForceRenderMarker] = useState(0);

    //-------------------------------------------------------------------------------UseEffects--------------------------------------------------------------------------------------
    useEffect(() => {
        if (posToFly) {
            map.setView(posToFly, 2);
        }
    }, [posToFly]);


    useEffect(() => {
        if(!mapState){
            updateMarkersByBounds();
        }
    }, [filters, filterState, mapState]);


    useEffect(() => {
        // Actualizar marcadores cuando el mapa se mueve
        const onMove = () => {
            if (!mapState) updateMarkersByBounds();
            if (mapState && earthQuakeChosen === undefined) updateEarthquakeMarkers();
        };
        map.on("move", onMove);

        return () => {
            map.off("move", onMove);
        };
    }, [stations, earthquakes, map, filters, filterState, mapState, earthQuakeChosen]);

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
        if (earthquakes.length > 0) {
            setForceRenderMarker((prev) => prev + 1);
        }
    }, [earthquakeAffectedStations]);

    useEffect(() => {
        removeOldKmls();
        setForceRenderMarker((prev) => prev + 1);
        removeAllStations();
    }, [earthQuakeChosen]);

    useEffect(() => {
        if (!showEarthquakeList) {
            removeOldKmls();
        }
    }, [showEarthquakeList]);

    //-------------------------------------------------------------------------------Funciones--------------------------------------------------------------------------------------

    const updateMarkersByBounds = () => {
        const mapBounds = map.getBounds();
        const mapEastCorner = mapBounds.getNorthEast();
        const mapWestCorner = mapBounds.getSouthWest();

        const filtered = stations?.filter(
            (s) =>
                s?.lat < mapEastCorner?.lat &&
                s?.lon < mapEastCorner?.lng &&
                s?.lat > mapWestCorner?.lat &&
                s?.lon > mapWestCorner?.lng,
        );

        const filteredMarkers =
            filters?.stationWithProblems || filters?.stationWithoutProblems ||
            (Array.isArray(filterState?.statusOption) &&
                filterState?.statusOption.length > 0) ||
            (Array.isArray(filterState?.typeOption) &&
                filterState?.typeOption.length > 0)
                ? filtered?.filter((s) =>
                      isStationFiltered(s, filterState, filters),
                  )
                : filtered;

        setMarkersByBounds(filteredMarkers);
    };

    const findStation = (s: StationAffectedInfo) => {
        return stations?.find(
            (station) =>
                station.network_code === s.network_code &&
                station.station_code === s.station_code,
        );
    };

    const updateEarthquakeMarkers = () => {
        
        // const mapBounds = map.getBounds();
        // const mapEastCorner = mapBounds.getNorthEast();
        // const mapWestCorner = mapBounds.getSouthWest();


        const filtered = earthquakes
        
        // earthquakes?.filter(
        //     (s) =>
        //         s?.lat < mapEastCorner?.lat &&
        //         s?.lon < mapEastCorner?.lng &&
        //         s?.lat > mapWestCorner?.lat &&
        //         s?.lon > mapWestCorner?.lng,
        // );

        setEarthquakesFiltered(filtered);
    };

    const earthquakeIcon =
        "https://maps.google.com/mapfiles/kml/shapes/star.png";

    const stationTooltip = (s: StationData) => {
        return (s.network_code?.toUpperCase() +
            "." +
            s.station_code?.toUpperCase()) as string;
    };

    const chosenToMap = () => {
        if (mapState) {
            return earthquakesFiltered as EarthquakeData[];
        } else {
            return markersByBounds as StationData[];
        }
    };

    const removeOldKmls = () => {
        map.eachLayer((layer) => {
            // Verifica si es una capa creada por omnivore
            if (!(layer instanceof L.TileLayer)) {
                map.removeLayer(layer);
            }
        });
    };

    const removeAllStations = () => {
        map.eachLayer((layer) => {
            if (layer instanceof L.Marker) {
                map.removeLayer(layer);
            }
        });
    };

    return (
        <>
            {mapState &&
            earthquakeAffectedStations !== undefined &&
            earthQuakeChosen !== undefined ? (
                <LoadKmzFromBase64
                    base64Data={earthquakeAffectedStations.kml}
                />
            ) : null}
            {mapState &&
                earthquakeAffectedStations &&
                earthquakeAffectedStations?.affected_stations?.map(
                    (s: StationAffectedInfo, index: number) => {
                        const station = findStation(s);
                        const uniqueKey = `affected-${station?.network_code}-${station?.station_code}-${index}-${forceRenderMarker}`;
                        return station && station.lat && station.lon ? (
                            <Marker
                                icon={chosenIcon(station as StationData)}
                                key={uniqueKey + forceRenderMarker}
                                position={[station.lat, station.lon]}
                            >
                                <Tooltip permanent={false}>
                                    <strong className="text-lg">
                                        {stationTooltip(station as StationData)}
                                    </strong>
                                </Tooltip>
                                <Popup maxWidth={600} minWidth={400}>
                                    <PopupChildren
                                        station={station as StationData}
                                        fromMain={true}
                                        mainParams={mainParams}
                                    />
                                </Popup>
                            </Marker>
                        ) : null;
                    },
                )}
            {markersByBounds &&
                chosenToMap()
                    .filter((s) => s?.lat != null && s?.lon != null)
                    .map((s: StationData | EarthquakeData, index: number) => {
                        const pos: LatLngExpression = [s.lat, s.lon];
                        const size: [number, number] =
                            s?.api_id === earthQuakeChosen?.api_id
                                ? [50, 50]
                                : [20, 20];
                        const color =
                            s?.api_id === earthQuakeChosen?.api_id
                                ? "light-red-icon"
                                : "yellow-icon";
                        const uniqueKey = `${s?.lat}-${s?.lon}-${s?.api_id ?? index}`;
                        if (mapState) {
                            if (
                                earthQuakeChosen === undefined ||
                                (earthQuakeChosen &&
                                    s.api_id === earthQuakeChosen.api_id)
                            ) {
                                return (
                                    <Marker
                                        icon={
                                            new L.Icon({
                                                iconUrl: earthquakeIcon,
                                                className: color,
                                                iconSize: size,
                                            })
                                        }
                                        eventHandlers={{
                                            click: () => {
                                                handleEarthquakeState(
                                                    s as EarthquakeData,
                                                );
                                                setForceSyncScrollerMap(
                                                    (prev) => prev + 1,
                                                );
                                                setForceRenderMarker(
                                                    (prev) => prev + 1,
                                                );
                                            },
                                        }}
                                        key={uniqueKey + forceRenderMarker}
                                        position={pos}
                                    />
                                );
                            }
                        } else {
                            const iconGaps = chosenIcon(s as StationData);
                            return (
                                <Marker
                                    icon={iconGaps}
                                    key={uniqueKey}
                                    position={pos}
                                >
                                    <Tooltip>
                                        <strong className="text-lg">
                                            {stationTooltip(s as StationData)}
                                        </strong>
                                    </Tooltip>
                                    <Popup maxWidth={600} minWidth={400}>
                                        <PopupChildren
                                            station={s as StationData}
                                            fromMain={true}
                                            mainParams={mainParams}
                                        />
                                    </Popup>
                                </Marker>
                            );
                        }
                    })}
        </>
    );
};

const Map = ({
    stations,
    initialCenter,
    mainParams,
    setMainParams,
    topoMap,
    filters,
    filterState,
    mapState,
    markersByBounds,
    earthquakes,
    setMarkersByBounds,
    earthquakesFiltered,
    setEarthquakesFiltered,
    handleEarthquakeState,
    posToFly,
    earthquakeAffectedStations,
    earthQuakeChosen,
    setForceSyncScrollerMap,
    showEarthquakeList,
    forceSyncDropLeftMap,
}: MapProps) => {
    //---------------------------------------------------------------------------UseStates--------------------------------------------------------------------------------------

    const [mapProps, setMapProps] = useState<MyMapContainerProps>({
        center: [0, 0],
        zoom: 4,
        scrollWheelZoom: true,
    });

    const [forceRender, setForceRender] = useState(0);

    //---------------------------------------------------------------------------UseEffects--------------------------------------------------------------------------------
    useEffect(() => {
        if (earthquakes.length > 0) {
            setForceRender((prev) => prev + 1);
        }
    }, [earthquakes]);

    useEffect(() => {
        const savedZoomLevel = localStorage.getItem("lastZoomLevel");

        const savedPosition = localStorage.getItem("lastPosition");

        const pos: LatLngExpression = initialCenter
            ? initialCenter
            : savedPosition
              ? (savedPosition
                    .split(",")
                    .map((s) => parseFloat(s)) as LatLngExpression)
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
    }, [mapState]);

    //---------------------------------------------------------------------------UseEscape--------------------------------------------------------------------------------------

    return (
        <div className="z-10 w-full flex justify-end">
            <MapContainer
                {...mapProps}
                key={forceRender + forceSyncDropLeftMap}
                preferCanvas={true}
                maxBoundsViscosity={1.0}
                worldCopyJump={true}
                zoomControl={false}
                className="w-full h-[92vh]"
            >
                <TileLayer
                    attribution={
                        topoMap
                            ? '&copy; <a href="https://www.opentopomap.org/copyright">OpenTopoMap</a> contributors'
                            : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    }
                    url={
                        topoMap
                            ? "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
                            : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    }
                    minZoom={4}
                />
                <ZoomControl position="bottomleft" />
                <ChangeView center={mapProps.center} zoom={mapProps.zoom} />

                    <MapMarkers
                        stations={stations}
                        initialCenter={initialCenter}
                        mainParams={mainParams}
                        setMainParams={setMainParams}
                        filters={filters}
                        filterState={filterState}
                        mapState={mapState}
                        markersByBounds={markersByBounds}
                        setMarkersByBounds={setMarkersByBounds}
                        earthquakesFiltered={earthquakesFiltered ? earthquakesFiltered : []}
                        setEarthquakesFiltered={setEarthquakesFiltered}
                        earthquakes={earthquakes}
                        handleEarthquakeState={handleEarthquakeState}
                        posToFly={posToFly}
                        earthquakeAffectedStations={earthquakeAffectedStations}
                        earthQuakeChosen={earthQuakeChosen}
                        setForceSyncScrollerMap={setForceSyncScrollerMap}
                        showEarthquakeList={showEarthquakeList}
                        forceSyncDropLeftMap={forceSyncDropLeftMap}
                    />
            </MapContainer>
        </div>
    );
};

export default Map;
