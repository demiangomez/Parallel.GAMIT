import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@hooks/useAuth";
import Layout from "@pages/Layout";

export const ProtectedRoute = () => {
    const { token } = useAuth();

    return token ? (
        <Layout>
            {" "}
            <Outlet />{" "}
        </Layout>
    ) : (
        <Navigate to="/auth/login" />
    );
};
export default ProtectedRoute;
