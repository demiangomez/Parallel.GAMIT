import { Navigate, Outlet } from "react-router-dom";

import { Toast } from "@componentsReact";
import { Layout } from "@pagesReact";

import { useUser, useAuth } from "@hooks";

import { apiMethods } from "@utils";

export const ProtectedRoute = () => {
    const { token } = useAuth();

    const {
        state: { status: userFetchStatus, method: userFetchMethod },
    } = useUser();

    let msg = null;

    if (
        userFetchStatus === "unAuthorized" &&
        apiMethods.includes(userFetchMethod)
    ) {
        if (userFetchMethod !== "get") {
            msg = (
                <Toast
                    error={true}
                    msg="You do not have permission to perform this action."
                />
            );
        } else {
            msg = (
                <Toast
                    error={true}
                    msg="You are not authorized to see some information."
                />
            );
        }
    }
    return token ? (
        <Layout>
            {userFetchStatus === "unAuthorized" && msg}
            <Outlet />
        </Layout>
    ) : (
        <Navigate to="/auth/login" />
    );
};
export default ProtectedRoute;
