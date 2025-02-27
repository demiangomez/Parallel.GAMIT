import React, { useEffect } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface NativePopupProps {
    map: L.Map;
    position: [number, number];
    children: React.ReactNode;
    maxWidth?: number;
    maxHeight?: number;
    minWidth?: number;
}

const NativePopup: React.FC<NativePopupProps> = ({ map, position, children, maxWidth, maxHeight, minWidth }) => {
    useEffect(() => {
        const popup = L.popup({ maxWidth, maxHeight, minWidth })
            .setLatLng(position)
            .setContent(React.isValidElement(children) ? children.props.children : children);

        popup.openOn(map);

        return () => {
            map.closePopup(popup);
        };
    }, [map, position, children, maxWidth, maxHeight, minWidth]);

    return null;
};

export default NativePopup;