import {
    Route,
    createBrowserRouter,
    RouterProvider,
    createRoutesFromElements,
} from "react-router-dom";

import {
    Error,
    Login,
    Main,
    Users,
    Station,
    Overview,
    Campaigns,
    Rinex,
} from "@pagesReact";

import { StationMain, StationPeople, StationVisits } from "@componentsReact";

import { ProtectedRoute, UnprotectedRoute } from "@routes/index";
import { AuthProvider } from "@hooks/useAuth";

const router = createBrowserRouter(
    createRoutesFromElements(
        <>
            <Route path="/auth" element={<UnprotectedRoute />}>
                <Route path="login" element={<Login />} />
                <Route path="*" element={<Error />} />
            </Route>
            <Route
                path="/"
                element={<ProtectedRoute />}
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
                        element={<Rinex />}
                        handle={{
                            crumb: () => {
                                return "Rinex";
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
                </Route>
                <Route path="*" element={<Error />} />
            </Route>
        </>,
    ),
);

function App() {
    return (
        <AuthProvider>
            <RouterProvider router={router} />
        </AuthProvider>
    );
}

export { router };
export default App;
