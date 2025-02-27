import L, { LatLngExpression } from "leaflet";
import { MapContainer, Marker, Popup, TileLayer, Tooltip, useMap, ZoomControl} from "react-leaflet";
import { useEffect, useState } from "react";
import { PopupChildren } from "@componentsReact";
import { useLocalStorage, useAuth, useApi } from "@hooks";
import { EarthquakeData, FilterState, GetParams, MyMapContainerProps, StationData, StationsAffectedServiceData, StationAffectedInfo, StationTypeServiceData,
StationStatusServiceData, StationStatusData , StationTypeData} from "@types";
import { isStationFiltered, chosenIcon, removeMarkersFromKml } from "@utils";
import { getStationTypesService, getStationStatusService} from "@services";

// @ts-expect-error leaflet omnivore doesnt have any types
import omnivore from "leaflet-omnivore";
import JSZip from "jszip";


interface MapProps {
    handleEarthquakeState: (earthquake: EarthquakeData) => void;
    initialCenter: LatLngExpression | undefined;
    posToFly: LatLngExpression | undefined;
    topoMap?: boolean | undefined;
    filters?: {
        openFilters: boolean;
        stationType: boolean;
        stationWithProblems: boolean;
        stationWithoutProblems: boolean;
        stationStatus: boolean;
    };
    filterState?: FilterState;
    forceSyncScrollerMap?: number;
    mapState: boolean;
    mainParams: GetParams;
    markersByBounds?: StationData[] | EarthquakeData[];
    earthquakes: EarthquakeData[];
    earthquakesFiltered: EarthquakeData[];
    earthquakeAffectedStations: StationsAffectedServiceData | undefined;
    earthQuakeChosen: EarthquakeData | undefined;
    stations: StationData[] | undefined;
    showEarthquakeList: boolean;
    setForceSyncScrollerMap: React.Dispatch<React.SetStateAction<number>>;
    setEarthquakesFiltered: React.Dispatch<React.SetStateAction<EarthquakeData[]>>;
    setMarkersByBounds: React.Dispatch<React.SetStateAction<StationData[] | EarthquakeData[] | undefined>>;
    setMainParams?: React.Dispatch<React.SetStateAction<GetParams>>;
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

//Component for adding kml render to leaflet map from kml in base64 format
const LoadKmzFromBase64 = ({ base64Data }: { base64Data: string }) => {
    const map = useMap();

    //--------------------------------------------------Funciones--------------------------------------------------
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
}: MapProps) => {

    //---------------------------------------------------------UseAuth-------------------------------------------------------------
        const { token, logout } = useAuth();
    
        //---------------------------------------------------------UseApi-------------------------------------------------------------
        const api = useApi(token, logout);

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

    //-------------------------------------------------------------------------------UseStates--------------------------------------------------------------------------------------
    const [forceRenderMarker, setForceRenderMarker] = useState(0);

    //-------------------------------------------------------------------------------UseEffects--------------------------------------------------------------------------------------
    //Modify setview when refreshing the page
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

    //Used for re rendering well when coming back to station mode from earthquake mode
    useEffect(() => {
        if(!mapState && markersByBounds && markersByBounds.length > 0){
            const zoom = map.getZoom();
            const pos = map.getCenter();
            
            map.setZoom(2);

            setTimeout(() => {
                map.setZoom(6);
            }, 500)

            setTimeout(() => {
                map.setZoom(10);
            }, 1200)

            setTimeout(() => {
                map.setZoom(4);
            }, 1800)

            setTimeout(() => {
                map.setZoom(zoom);
                map.setView(pos);
            },  2900);
        }
    }, [mapState])

    // Updates markers when map moves
    useEffect(() => {
        const onMove = () => {
            if (!mapState) updateMarkersByBounds();
            if (mapState && earthQuakeChosen === undefined) updateEarthquakeMarkers();
        };
        map.on("move", onMove);

        return () => {
            map.off("move", onMove);
        };
    }, [stations, earthquakes, map, filters, filterState, mapState, earthQuakeChosen]);

    //Updates storage when you modify zoom and position
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

    // Update markers when initialcenter changes
    useEffect(() => {
        if (initialCenter) {
            if(!mapState){
                map.setView(
                    initialCenter,
                    lastZoomLevel ? parseInt(lastZoomLevel) : 8,
                );
                updateMarkersByBounds();
            }
        }
    }, [initialCenter, map]);

    useEffect(() => {
        updateMarkersByBounds();
    },[])

    // Forces map and marker renders when you get earthquake affected stations
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

    //-------------------------------------------------------------------------------Funciones--------------------------------------------------------------------------------------
    //Update markers considering map bounds in viewport
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
    
        const filtered = earthquakes
        
        setEarthquakesFiltered(filtered);
    };

    const earthquakeIcon = "https://maps.google.com/mapfiles/kml/shapes/star.png";

    const stationTooltip = (s: StationData) => {
        return (s.network_code?.toUpperCase() +
            "." +
            s.station_code?.toUpperCase()) as string;
    };

    const earthquakeToolTip = (s: EarthquakeData) => {
        return (s.location?.toUpperCase() + " (M " + s.mag?.toString().toUpperCase() + ")") as string;
    }

    //choses what markers show on the map according to the map state
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

    const [types, setTypes] = useState<{image:string, name: string}[]>([]);
    const [statuses, setStatuses] = useState<{name: string, color: string}[]>([]);

    const getStationStatuses = async () =>{
        try {
            const res = await getStationStatusService<StationStatusServiceData>(api);
            if(res){
                const statuses = res.data.map((status: StationStatusData) => {
                    return {
                        color: status.color_name,
                        name: status.name,
                    }
                })
                setStatuses(statuses)
            }
        } catch (err) {
            console.error(err);
        }
    }

    const getStationTypes = async () =>{
        try {
            const res = await  getStationTypesService<StationTypeServiceData>(api);
            if(res){
                const types = res.data.map((type: StationTypeData) => {
                    return {
                        image: type.actual_image,
                        name: type.name
                    }
                })
                setTypes(types)
        }
        } catch (err) {
            console.error(err);
        }
    }

    useEffect(() => {
        getStationStatuses();
        getStationTypes();
    },[])

    const removeAllStations = () => {
        map.eachLayer((layer) => {
            if (layer instanceof L.Marker) {
                map.removeLayer(layer);
            }
        });
    };

    const [isDangerousPopup, setIsDaangerousPopup] = useState<boolean>(false)

    const isNearTop = (station: StationData) => {
        const result = (station.lat)
        if(85.0511 - 3.8 < result){
            map.setView([station.lat, station.lon], 10);
            setIsDaangerousPopup(true);
        }
    };

    useEffect(() => {
        if(isDangerousPopup){
            map.setMinZoom(10);             
        }
        else if(!isDangerousPopup){
            map.setMinZoom(4);
        }
    }, [isDangerousPopup])

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
                                icon={chosenIcon(station as StationData, types, statuses)}
                                key={uniqueKey + forceRenderMarker}
                                position={[station.lat, station.lon]}
                                eventHandlers={{
                                    click: () => {
                                        isNearTop(station as StationData);
                                    },
                                    popupclose: () => {
                                        setIsDaangerousPopup(false);
                                    }
                                }}
                            >
                                <Tooltip permanent={false}>
                                    <strong className="text-lg">
                                        {stationTooltip(station as StationData)}
                                    </strong>
                                </Tooltip>
                                <Popup maxWidth={600} minWidth={400}
                                >
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
            {(markersByBounds) &&
                chosenToMap()
                    .filter((s) => s?.lat != null && s?.lon != null)
                    .map((s: StationData | EarthquakeData, index: number) => {
                        const pos: LatLngExpression = [s.lat, s.lon];
                        const size: [number, number] =
                            s?.api_id === earthQuakeChosen?.api_id
                                ? [40, 40]
                                : [30, 30];
                        const color =
                            s?.api_id === earthQuakeChosen?.api_id
                                ? "light-red-icon"
                                : "yellow-icon";
                        const uniqueKey = `${s?.lat}-${s?.lon}-${s?.api_id ?? index}`;
                        if (mapState) 
                        {
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
                                                isNearTop(s as StationData);
                                            },
                                            popupclose: () => {
                                                setIsDaangerousPopup(false);
                                            }
                                        }}
                                        key={uniqueKey + forceRenderMarker}
                                        position={pos}
                                    >
                                        <Tooltip>
                                                <strong className="text-lg">
                                                    {earthquakeToolTip(s as EarthquakeData)}
                                                </strong>
                                        </Tooltip>
                                    </Marker>
                                );
                            }
                        } 
                        else 
                        {
                            const iconGaps = chosenIcon(s as StationData, types, statuses);
                                return (
                                    <Marker
                                        icon={iconGaps}
                                        key={uniqueKey}
                                        position={pos}
                                        eventHandlers={{
                                            click: () => {
                                                isNearTop(s as StationData);
                                            },
                                            popupclose: () => {
                                                setIsDaangerousPopup(false);
                                            }
                                        }}
                                    >
                                        <Tooltip>
                                            <strong className="text-lg">
                                                {stationTooltip(s as StationData)}
                                            </strong>
                                        </Tooltip>
                                        <Popup maxWidth={600} minWidth={400}
                                        eventHandlers={{
                                            
                                        }}
                                        >
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
    initialCenter,
    posToFly,
    handleEarthquakeState,
    topoMap,
    filters,
    filterState,
    mainParams,
    mapState,
    markersByBounds,
    earthquakes,
    earthquakesFiltered,
    earthquakeAffectedStations,
    earthQuakeChosen,
    stations,
    showEarthquakeList,
    setForceSyncScrollerMap,
    setEarthquakesFiltered,
    setMarkersByBounds,
    setMainParams,

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
                key={forceRender}
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
                <ZoomControl position="bottomright" />
                <ChangeView center={mapProps.center} zoom={mapProps.zoom} />

                    <MapMarkers
                        posToFly={posToFly}
                        initialCenter={initialCenter}
                        handleEarthquakeState={handleEarthquakeState}
                        filters={filters}
                        filterState={filterState}
                        mapState={mapState}
                        mainParams={mainParams}
                        markersByBounds={markersByBounds}
                        earthquakes={earthquakes}
                        earthQuakeChosen={earthQuakeChosen}
                        earthquakesFiltered={earthquakesFiltered ? earthquakesFiltered : []}
                        earthquakeAffectedStations={earthquakeAffectedStations}
                        stations={stations}
                        setMainParams={setMainParams}
                        setMarkersByBounds={setMarkersByBounds}
                        setEarthquakesFiltered={setEarthquakesFiltered}
                        setForceSyncScrollerMap={setForceSyncScrollerMap}
                        showEarthquakeList={showEarthquakeList}
                    />
            </MapContainer>
        </div>
    );
};

export default Map;
