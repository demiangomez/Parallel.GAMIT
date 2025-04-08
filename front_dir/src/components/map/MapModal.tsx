import React, { useEffect, useState} from "react";
import { EditControl} from "react-leaflet-draw";
import { MapSkeleton, Modal} from "@componentsReact";
import { MapContainer, TileLayer, FeatureGroup, useMap} from "react-leaflet";
import { LatLngExpression, latLng} from "leaflet";
import { useLocalStorage} from "@hooks";
import { MyMapContainerProps, StationStatusServiceData, StationStatusData, StationTypeServiceData, StationTypeData, StationServiceData, StationData} from "@types";
import StationCreateMap from "./StationCreateMap";
import { getStationTypesService, getStationStatusService, getStationsService } from "@services";
import { useAuth, useApi } from "@hooks";
interface MapModalProps {
    setShowMapModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
    handleDrawPolygon: (e: any) => void;
    markerType: "marker" | "polygon"
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
    setShowMapModal,
    handleDrawPolygon,
    markerType,
}: MapModalProps) => {

    const { token, logout } = useAuth();
    
    const api = useApi(token, logout);


    //-----------------------------------------------------Funciones-----------------------------------------------------

    const handleCloseModal = () => {};

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
    
    const getStations = async () => {
                try {
                    const result = await getStationsService<StationServiceData>(
                        api,
                    );
                    if (result) {
                        setStations(result.data);
                    }
                } catch (err) {
                    console.error(err);
                }
            };

    const getStationTypes = async () => {
        try {
            const res =
                await getStationTypesService<StationTypeServiceData>(api);
            if (res) {
                const types = res.data.map((type: StationTypeData) => {
                    return {
                        image: type.actual_image,
                        name: type.name,
                    };
                });
                setTypes(types);
            }
        } catch (err) {
            console.error(err);
        }
    };

    

    //-----------------------------------------------------UseState------------------------------------------------------

    const [stations, setStations] = useState<StationData[] | undefined>(
        undefined,
    );

    const [types, setTypes] = useState<{ image: string; name: string }[]>([]);
    
    const [statuses, setStatuses] = useState<{ name: string; color: string }[]>(
        [],
    );

    const [isMarkerSelected, setIsMarkerSelected] = useState(false);

    const [currentMarker, setCurrentMarker] = useState<{
        lat: number;
        lng: number;
    } | null>(null);

    const [mapProps, setMapProps] = useState<MyMapContainerProps>({
        center: [0, 0],
        zoom: 4,
        scrollWheelZoom: true,
    });

    const [loadingMap, setLoadingMap] = useState(false);
    
    const [rangeValue, setRangeValue] = useState(40);

    const memoizedEditControl = React.useMemo(() => (
        !isMarkerSelected && 
        <EditControl
            position="topright"
            onCreated={(e) => {
                handleDrawPolygon(e);
                setIsMarkerSelected(true);
                setCurrentMarker({
                    lat: e.layer._latlng.lat,
                    lng: e.layer._latlng.lng,
                });
            }}
            onDeleted={() => {
                setIsMarkerSelected(false);
            }}
            draw={{
                rectangle: false,
                polyline: false,
                circle: false,
                marker: markerType === "marker" && !isMarkerSelected,
                circlemarker: false,
                polygon: markerType === "polygon"
            }}
        />
    ), [markerType, isMarkerSelected, handleDrawPolygon]);


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

    



    useEffect(() => {
        if(markerType === "marker") {
            setLoadingMap(true);
            Promise.all([
                getStations(),
                getStationStatuses(),
                getStationTypes()
            ]).then(() => {
                setLoadingMap(false);
            });
        }
        }, [markerType]);




    return (
        <Modal
            close={true}
            modalId="map"
            size="md"
            handleCloseModal={handleCloseModal}
            setModalState={setShowMapModal}
        >
            { (loadingMap && markerType === "marker") ? <MapSkeleton /> :
            <div className="flex flex-col justify-center items-center gap-y-4">
                <h1 className="text-2xl font-bold text-gray-800">Select Coordinates</h1>

                <MapContainer
                    {...mapProps}
                    preferCanvas={true}
                    zoomControl={false}
                    maxBoundsViscosity={1.0}
                    worldCopyJump={true}
                    className="w-[90vw] h-[60vh] md:w-[70vw] md:h-[70vh] xl:w-[60vw] lg:h-[80vh] max-w-[1000px] max-h-[600px]"
                >
                    {  markerType === "marker" && isMarkerSelected &&
                        <div className="z-[999999999] bg-white absolute top-2 left-2 p-2 rounded-md w-48">
                            <input 
                                type="range" 
                                className="range range-xs range-neutral w-full"
                                value={rangeValue}
                                onChange={(e) => setRangeValue(parseInt(e.target.value))}
                                step="10"
                                min="0"
                                max="1000"
                            />
                            <label className="font-bold text-sm mb-1 block">{"Radius: " + rangeValue + " KM"}</label>
                        </div>
                    }
                    { markerType === "marker" && isMarkerSelected &&
                        <StationCreateMap 
                        stations={stations} 
                        statuses={statuses} 
                        types={types}
                        mapProps={mapProps}
                        rangeValue={rangeValue}
                        currentMarker={currentMarker}
                        />
                    }
                    <ChangeView center={mapProps.center} zoom={mapProps.zoom} />
                    <SetView />
                    <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        minZoom={4}
                    />
                    <FeatureGroup>
                        {memoizedEditControl}
                    </FeatureGroup>
                </MapContainer>
            </div>
            }
        </Modal>
    );
};

export default MapModal;
