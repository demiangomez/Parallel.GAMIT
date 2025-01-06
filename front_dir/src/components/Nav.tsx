import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
    ArrowRightEndOnRectangleIcon,
    MegaphoneIcon,
    ServerIcon,
    Squares2X2Icon,
    UserCircleIcon,
    UserGroupIcon,
} from "@heroicons/react/24/outline";

import { useApi, useAuth } from "@hooks";

import { getServerHealthService } from "@services";
import { ErrorResponse } from "@types";

import { jwtDeserializer } from "@utils";

type healthCheck = {
    result: string;
    statusCode: number;
};

const Nav = () => {
    const { logout, token, userPhoto } = useAuth();
    const api = useApi(token, logout);

    const tokenDeserialized = jwtDeserializer(token as string);
    const userName = tokenDeserialized?.username;

    const [serverHealth, setServerHealth] = useState<healthCheck | null>(null);

    const serverHealthCheck = async () => {
        try {
            const res = await getServerHealthService<
                healthCheck | ErrorResponse
            >(api);
            if ("status" in res) {
                setServerHealth({
                    result: res?.response?.errors[0]?.detail,
                    statusCode: res.statusCode,
                });
            } else {
                setServerHealth(res);
            }
        } catch (err) {
            setServerHealth({
                result: "Server is down",
                statusCode: 500,
            });
            console.error(err);
        }
    };

    useEffect(() => {
        serverHealthCheck();

        const intervalId = setInterval(serverHealthCheck, 30000);

        return () => clearInterval(intervalId);
    }, []); // eslint-disable-line

    return (
        <div
            className="navbar bg-gray-800 text-white"
            style={{ maxHeight: "none", minHeight: "8vh" }}
        >
            <div className="navbar-start">
                <div
                    className="indicator ml-4"
                    title={serverHealth ? serverHealth.result : ""}
                >
                    <ServerIcon
                        fill="none"
                        className="size-7"
                        strokeWidth={2}
                    />
                    <span
                        className={`badge badge-xs badge-${serverHealth ? (serverHealth?.statusCode === 200 ? "success" : "error") : "neutral"} indicator-item`}
                    ></span>
                </div>
            </div>
            <div className="navbar-center">
                <Link to={"/"} className="text-2xl ml-6">
                    Parallel.GAMIT
                </Link>
            </div>
            <div className="navbar-end">
                <Link
                    className="btn btn-ghost btn-circle"
                    to={"/campaigns"}
                    title="Campaigns"
                >
                    <MegaphoneIcon className="size-8" />
                </Link>
                <Link
                    className="btn btn-ghost btn-circle"
                    to={"/overview"}
                    title="Overview"
                >
                    <Squares2X2Icon className="size-8" />
                </Link>
                <div className="dropdown dropdown-end">
                    <div
                        tabIndex={0}
                        role="button"
                        className="btn btn-ghost btn-circle avatar"
                        title="User"
                    >
                        {!userPhoto ? (
                            <UserCircleIcon className="size-8" />
                        ) : (
                            <img
                                alt="User"
                                className="rounded-full w-6 h-6"
                                src={`data:image/*;base64,${userPhoto}`}
                            />
                        )}
                    </div>
                    <ul
                        tabIndex={0}
                        className="menu menu-sm dropdown-content mt-3 z-[10000000000000000] space-y-1 p-2 shadow bg-gray-800 border-[1px] border-gray-600 rounded-box w-52"
                    >
                        <div className=" border-b-[1px] border-gray-600 flex justify-center">
                            <span className="mb-2">
                                <strong>{userName?.toUpperCase()}</strong>
                            </span>
                        </div>
                        <li className="">
                            <Link
                                className="hover:bg-slate-600 flex justify-start focus:text-primary"
                                to={"/users"}
                            >
                                <UserGroupIcon className="size-6" />

                                <span className="ml-[40px]">Users</span>
                            </Link>
                        </li>
                        <li className="">
                            <a
                                className="hover:bg-slate-600 flex w-full justify-start"
                                onClick={() => logout(true)}
                            >
                                <ArrowRightEndOnRectangleIcon className="size-6" />

                                <span className="ml-[40px]">Logout</span>
                            </a>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    );
};

export default Nav;
