import { LatLngExpression } from "leaflet";

import { Marker, Tooltip } from "react-leaflet";
import { useMemo } from "react";

import { StationData } from "@types";

import { chosenIcon } from "@utils";

interface StationCreateMapProps {
    stations: StationData[] | undefined;
    types: { image: string; name: string }[];
    statuses: { name: string; color: string }[];
    mapProps: {
        center: LatLngExpression;
        zoom: number;
    };
    rangeValue: number;
    currentMarker: {
        lat: number;
        lng: number;
    } | null;
}

const StationCreateMap = ({
    stations,
    types,
    statuses,
    rangeValue,
    currentMarker,
}: StationCreateMapProps) => {
    const stationTooltip = (s: StationData) => {
        return (s.network_code?.toUpperCase() +
            "." +
            s.station_code?.toUpperCase()) as string;
    };

    const calculateDistance = (
        lat1: number,
        lon1: number,
        lat2: number,
        lon2: number,
    ): number => {
        const lat1Rad = (lat1 * Math.PI) / 180;
        const lat2Rad = (lat2 * Math.PI) / 180;
        const lon1Rad = (lon1 * Math.PI) / 180;
        const lon2Rad = (lon2 * Math.PI) / 180;

        const h =
            Math.sin((lat2Rad - lat1Rad) / 2) ** 2 +
            Math.cos(lat1Rad) *
                Math.cos(lat2Rad) *
                Math.sin((lon2Rad - lon1Rad) / 2) ** 2;

        return 2 * 6371000 * Math.asin(Math.sqrt(h));
    };

    const isWithinDistance = (
        lat1: number,
        lon1: number,
        lat2: number,
        lon2: number,
        maxDistance: number,
    ): boolean => {
        return calculateDistance(lat1, lon1, lat2, lon2) <= maxDistance * 1000;
    };

    const stationsInRange = useMemo(() => {
        if (!stations || !Array.isArray(stations) || !currentMarker) {
            return [];
        }

        return stations
            .filter((station) => {
                if (!station.lat || !station.lon) return false;
                return isWithinDistance(
                    currentMarker.lat,
                    currentMarker.lng,
                    station.lat,
                    station.lon,
                    rangeValue,
                );
            })
            .map((s, index) => {
                if (!s.lat || !s.lon) return null;
                const uniqueKey = `${s.lat}-${s.lon}-${s.api_id ?? index}`;
                const iconGaps = chosenIcon(s, types, statuses);
                const pos: LatLngExpression = [s.lat, s.lon];

                return (
                    <Marker icon={iconGaps} key={uniqueKey} position={pos}>
                        <Tooltip>
                            <strong className="text-lg">
                                {stationTooltip(s)}
                            </strong>
                        </Tooltip>
                    </Marker>
                );
            });
    }, [stations, currentMarker, rangeValue]);

    if (!stations || !Array.isArray(stations) || !currentMarker) {
        return null;
    }

    return <>{stationsInRange}</>;
};

export default StationCreateMap;
