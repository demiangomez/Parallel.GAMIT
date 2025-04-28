import { Nav } from "@componentsReact";
import { useAuth } from "@hooks/useAuth";
import { ReactNode } from "react";

interface LayoutProps {
    children: ReactNode;
}

const Layout = ({ children }: LayoutProps) => {
    const { token } = useAuth();
    const containerDiv = token
        ? "flex flex-col flex-auto max-w-[100vw] min-h-[92vh]"
        : "flex flex-col flex-auto max-w-[100vw] min-h-[100vh] p-4";
    return (
        <>
            {token && <Nav />}
            <div className={containerDiv}>{children}</div>

            {/* {token && (
                <footer className="flex justify-center items-center min-h-[4vh] bg-gray-50 text-black border-t-[1px]">
                    <p>Footer</p>
                </footer>
            )} */}
        </>
    );
};

export default Layout;
