import { createContext, useEffect, useMemo, useState } from "react";
import type { Location } from "react-router-dom";
import { useLocation, useNavigate } from "react-router-dom";

type NavigationProviderProps = {
    children: React.ReactNode;
};

interface NavigationBundle {
    from: Location | undefined;
    to: Location | undefined;
}

const NavigationProvider: React.FC<NavigationProviderProps> = ({
    children,
}: NavigationProviderProps) => {
    const defaultNavigationBundle = {
        from: undefined,
        to: undefined,
    };

    const NavigationContext = createContext<NavigationBundle>(
        defaultNavigationBundle,
    );

    const [from, setFrom] = useState<Location | undefined>(undefined);
    const [to, setTo] = useState<Location | undefined>(undefined);
    const location = useLocation();
    const navigate = useNavigate();

    useEffect(() => {
        setFrom(location);
    }, [location]);

    useEffect(() => {
        const unlisten = navigate((location, action) => {
            if (action === "POP") setTo(location);
        });
        return unlisten;
    }, [navigate]);

    const navigationBundle = useMemo(() => {
        return {
            from,
            to,
        };
    }, [from, to]);

    return (
        <NavigationContext.Provider value={navigationBundle}>
            {children}
        </NavigationContext.Provider>
    );
};

export default NavigationProvider;
