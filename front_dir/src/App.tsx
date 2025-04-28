import {
    Route,
    createBrowserRouter,
    RouterProvider,
    createRoutesFromElements,
} from "react-router-dom";

import "global";

import {
    Error,
    Login,
    Main,
    Users,
    Station,
    Overview,
    Campaigns,
} from "@pagesReact";

import {
    StationEvents,
    StationMain,
    StationPeople,
    StationRinex,
    StationTimeSeries,
    StationVisits,
    StationSources,
    SourcesServers,
} from "@componentsReact";

import { ProtectedRoute, UnprotectedRoute } from "@routes";

import { AuthProvider } from "@hooks/useAuth";
import { UserContextProvider } from "@hooks/user/userInfo.context";

const router = createBrowserRouter(
    createRoutesFromElements(
        <>
            <Route path="/auth" element={<UnprotectedRoute />}>
                <Route path="login" element={<Login />} />
                <Route path="*" element={<Error />} />
            </Route>
            <Route
                path="/"
                element={<ProtectedRoute />} // Aquí debe estar la lógica de autorización
                handle={{
                    crumb: () => {
                        return "Home";
                    },
                }}
            >
                <Route index element={<Main />} />
                <Route
                    path="campaigns"
                    element={<Campaigns />}
                    handle={{
                        crumb: () => {
                            return "campaigns";
                        },
                    }}
                />
                <Route
                    path="sources"
                    element={<SourcesServers />}
                    handle={{
                        crumb: () => {
                            return "sources-servers";
                        },
                    }}
                />
                <Route
                    path="overview"
                    element={<Overview />}
                    handle={{
                        crumb: () => {
                            return "overview";
                        },
                    }}
                />
                <Route
                    path="users"
                    element={<Users />}
                    handle={{
                        crumb: () => {
                            return "Users";
                        },
                    }}
                />
                <Route
                    path=":nc/:sc"
                    element={<Station />}
                    handle={{
                        crumb: () => {
                            return "Station";
                        },
                    }}
                >
                    <Route index element={<StationMain />} />
                    <Route
                        path="rinex"
                        element={<StationRinex />}
                        handle={{
                            crumb: () => {
                                return "Rinex";
                            },
                        }}
                    />
                    <Route
                        path="sources"
                        element={<StationSources />}
                        handle={{
                            crumb: () => {
                                return "Sources";
                            },
                        }}
                    />
                    <Route
                        path="people"
                        element={<StationPeople />}
                        handle={{
                            crumb: () => {
                                return "People";
                            },
                        }}
                    />
                    <Route
                        path="visits"
                        element={<StationVisits />}
                        handle={{
                            crumb: () => {
                                return "Visits";
                            },
                        }}
                    />
                    <Route
                        path="timeseries"
                        element={<StationTimeSeries />}
                        handle={{
                            crumb: () => {
                                return "Time Series";
                            },
                        }}
                    />
                    <Route
                        path="events"
                        element={<StationEvents />}
                        handle={{
                            crumb: () => {
                                return "Events";
                            },
                        }}
                    />
                </Route>
                <Route path="*" element={<Error />} />
            </Route>
        </>,
    ),
    {
        future: {
            v7_relativeSplatPath: true,
            v7_fetcherPersist: true,
            v7_normalizeFormMethod: true,
            v7_partialHydration: true,
            v7_skipActionErrorRevalidation: true,
        },
    },
);

function App() {
    return (
        <UserContextProvider>
            <AuthProvider>
                <RouterProvider
                    router={router}
                    future={{ v7_startTransition: true }}
                />
            </AuthProvider>
        </UserContextProvider>
    );
}

export { router }; //eslint-disable-line
export default App;
