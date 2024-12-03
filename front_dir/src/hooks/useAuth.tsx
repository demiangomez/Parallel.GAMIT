import {
    createContext,
    ReactNode,
    useContext,
    useEffect,
    useMemo,
    useState,
} from "react";

import { Navigate } from "react-router-dom";

import { useLocalStorage } from "@hooks/useLocalStorage";
import useApi from "@hooks/useApi";

import { jwtDeserializer } from "@utils";
import { getUserPhotoService } from "@services";

interface AuthContextProps {
    token: string | null;
    role: string | null;
    refreshToken: string | null;
    refresh: boolean | null;
    userPhoto: string | null;
    login: (token: string | null, nav?: boolean, lastPath?: string) => void;
    logout: (href: boolean) => void;
    getRole: (role: string) => void;
    getUserPhoto: () => void;
    loginRefresh: (token: string | null) => void;
    setRefresh: (refresh: boolean | null) => void;
    setRefreshToken: (token: string | null) => void;
    setUserPhoto: (photo: string | null) => void;
}

interface AuthProviderProps {
    children: ReactNode;
}

const AuthContext = createContext<AuthContextProps>({
    token: null,
    role: null,
    refresh: null,
    refreshToken: null,
    userPhoto: null,
    login: () => {},
    logout: () => {},
    getRole: () => {},
    loginRefresh: () => {},
    getUserPhoto: () => {},
    setRefresh: () => {},
    setRefreshToken: () => {},
    setUserPhoto: () => {},
});

export const AuthProvider = ({ children }: AuthProviderProps) => {
    const [token, setToken] = useLocalStorage("gpsToken", null);
    const [refreshToken, setRefreshToken] = useLocalStorage("gpsRefresh", null);
    const [role, setRole] = useLocalStorage("gpsRole", null);

    const [userPhoto, setUserPhoto] = useState<string | null>(null);

    const [refresh, setRefresh] = useState<boolean | null>(null);

    const login = (token: string | null, nav?: boolean) => {
        if (token) {
            setToken(token);
            setRefresh(null);
            <Navigate to="/" replace />;
        }
        if (token && nav) {
            setToken(token);
            setRefresh(null);
            window.history.back();
            // navigate(lastPath);
        }
    };

    const loginRefresh = (token: string | null) => {
        if (token) {
            setRefreshToken(token);
        }
    };

    const logout = (href: boolean) => {
        setToken(null);
        setRefreshToken(null);
        setRefresh(null);
        setRole(null);
        if (href) <Navigate to="/auth/login" />;
    };

    const getRole = (role: string) => {
        setRole(role);
    };

    const api = useApi(token, logout);

    const getUserPhoto = async () => {
        try {
            const token = localStorage.getItem("gpsToken");
            const tokenDeserialized = jwtDeserializer(token as string);
            if (token) {
                const res = await getUserPhotoService<any>(
                    api,
                    Number(tokenDeserialized?.user_id),
                );
                if (res.statusCode === 200) {
                    setUserPhoto(res.photo);
                }
            }
        } catch (err) {
            console.error(err);
        }
    };

    useEffect(() => {
        const interval = setInterval(() => {
            const tokenTest = localStorage.getItem("gpsToken");
            const refreshTest = localStorage.getItem("gpsRefresh");
            const tokenDeserialized = jwtDeserializer(tokenTest as string);
            if (tokenDeserialized) {
                getRole(tokenDeserialized.role_id.toString());
                const currentTime = Date.now() / 1000;
                // 1716307200
                // tokenDeserialized.exp
                if (tokenDeserialized.exp < currentTime) {
                    setRefresh(true);
                    setToken(null);

                    // logout(true);
                }
            }
            if (tokenTest === null && refreshTest === null) {
                logout(true);
            }
            if (tokenTest !== null && refreshTest === null) {
                setRefresh(false);
            }
            if (tokenTest === null && refreshTest !== null) {
                setRefresh(true);
            }
        }, 500);

        return () => {
            clearInterval(interval);
        };
    }, []);

    useEffect(() => {
        getUserPhoto();
    }, [token]);

    const value = useMemo(
        () => ({
            token,
            role,
            refresh,
            login,
            logout,
            userPhoto,
            refreshToken,
            loginRefresh,
            getRole,
            getUserPhoto,
            setRefresh,
            setRefreshToken,
            setUserPhoto,
        }),
        [token, refresh, role, userPhoto],
    );

    return (
        <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
};
