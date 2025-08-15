import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";

type Position = {
    lat: number;
    lon: number;
};

type Displacement = {
    north: number; // Desplazamiento en metros hacia el norte (componente V)
    east: number; // Desplazamiento en metros hacia el este (componente U)
};

type Props = {
    origin: Position;
    displacement: Displacement;
    magnitude: number;
};

const MapVector = ({ origin, displacement, magnitude }: Props) => {
    const map = useMap();
    const arrowRef = useRef<L.LayerGroup | null>(null);

    const updateArrow = () => {
        if (arrowRef.current) {
            map.removeLayer(arrowRef.current);
        }

        // ✅ CALCULAR MAGNITUD REAL DEL DESPLAZAMIENTO
        const realMagnitude = Math.sqrt(
            displacement.north * displacement.north +
                displacement.east * displacement.east,
        );

        const PIXEL_SIZE =
            realMagnitude <= 1
                ? 100
                : realMagnitude <= 1.5
                  ? 200
                  : realMagnitude <= 1.75
                    ? 250
                    : realMagnitude <= 2
                      ? 300
                      : realMagnitude <= 2.5
                        ? 400
                        : realMagnitude <= 3
                          ? 500
                          : realMagnitude <= 5
                            ? 600
                            : realMagnitude <= 7
                              ? 400
                              : realMagnitude <= 9
                                ? 400
                                : realMagnitude <= 10
                                  ? 400
                                  : 500;

        // ✅ CALCULAR ÁNGULO DEL VECTOR
        const vectorAngle = Math.atan2(displacement.east, displacement.north);

        // ✅ OBTENER POSICIÓN EN PÍXELES DEL ORIGEN
        const originPixel = map.latLngToContainerPoint([
            origin.lat,
            origin.lon,
        ]);

        // ✅ CALCULAR POSICIÓN FINAL EN PÍXELES
        const endPixel = {
            x: originPixel.x + PIXEL_SIZE * Math.sin(vectorAngle),
            y: originPixel.y - PIXEL_SIZE * Math.cos(vectorAngle),
        };

        // ✅ CONVERTIR POSICIÓN FINAL A COORDENADAS
        const endLatLng = map.containerPointToLatLng([endPixel.x, endPixel.y]);
        const endPosition = { lat: endLatLng.lat, lon: endLatLng.lng };

        // ✅ CALCULAR LONGITUD DE PUNTA EN PÍXELES
        const arrowHeadPixelLength = PIXEL_SIZE * 0.1;

        // ✅ CALCULAR PUNTAS EN PÍXELES
        const leftHeadPixel = {
            x:
                endPixel.x -
                arrowHeadPixelLength * Math.sin(vectorAngle + Math.PI / 6),
            y:
                endPixel.y +
                arrowHeadPixelLength * Math.cos(vectorAngle + Math.PI / 6),
        };

        const rightHeadPixel = {
            x:
                endPixel.x -
                arrowHeadPixelLength * Math.sin(vectorAngle - Math.PI / 6),
            y:
                endPixel.y +
                arrowHeadPixelLength * Math.cos(vectorAngle - Math.PI / 6),
        };

        // ✅ CONVERTIR PUNTAS A COORDENADAS
        const leftHeadLatLng = map.containerPointToLatLng([
            leftHeadPixel.x,
            leftHeadPixel.y,
        ]);
        const rightHeadLatLng = map.containerPointToLatLng([
            rightHeadPixel.x,
            rightHeadPixel.y,
        ]);

        // ✅ CUERPO DE LA FLECHA
        const mainLine = L.polyline(
            [
                [origin.lat, origin.lon],
                [endPosition.lat, endPosition.lon],
            ],
            {
                color: "red",
                weight: Math.max(2, Math.min(6, magnitude / 2)),
                opacity: 0.8,
            },
        );

        // ✅ PUNTA IZQUIERDA
        const leftArrow = L.polyline(
            [
                [leftHeadLatLng.lat, leftHeadLatLng.lng],
                [endPosition.lat, endPosition.lon],
            ],
            {
                color: "red",
                weight: Math.max(1, Math.min(4, magnitude / 3)),
                opacity: 0.8,
            },
        );

        // ✅ PUNTA DERECHA
        const rightArrow = L.polyline(
            [
                [rightHeadLatLng.lat, rightHeadLatLng.lng],
                [endPosition.lat, endPosition.lon],
            ],
            {
                color: "red",
                weight: Math.max(1, Math.min(4, magnitude / 3)),
                opacity: 0.8,
            },
        );

        const group = L.layerGroup([mainLine, leftArrow, rightArrow]).addTo(
            map,
        );
        arrowRef.current = group;
    };

    useEffect(() => {
        updateArrow();

        return () => {
            if (arrowRef.current) {
                map.removeLayer(arrowRef.current);
            }
        };
    }, [origin, displacement, magnitude, map]);

    useEffect(() => {
        map.on("zoomend", updateArrow);

        return () => {
            map.off("zoomend", updateArrow);
        };
    }, [origin, displacement, magnitude, map]);

    return null;
};

export default MapVector;
