import { FormEvent, useEffect, useState } from "react";
import { Toast, Modal } from "@componentsReact";
import { AxiosError } from "axios";

import osupng from "@assets/images/logo-osu-01.png";

import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { useAuth } from "@hooks";

import { loginService, refreshTokenService } from "@services";

import { showModal } from "@utils";
import { Errors, LoginServiceData } from "@types";

const Login = () => {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");

    const [message, setMessage] = useState<{
        error: boolean | undefined;
        msg: string;
        errors?: Errors;
    }>({ error: undefined, msg: "", errors: undefined });

    const [loading, setLoading] = useState(false);

    const { refresh, refreshToken, login, loginRefresh, setRefreshToken } =
        useAuth();

    const closeToast = () => {
        setMessage({ error: undefined, msg: "" });
    };

    const handleLogin = async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();

        try {
            setLoading((prev) => !prev);
            closeToast();
            // Login service
            const response = await loginService<LoginServiceData>(
                username,
                password,
            );
            // Save token in localstorage and navigate to home
            loginRefresh(response.refresh);
            login(response.access);
            setMessage({ error: false, msg: "Login successfull" });

            return;
        } catch (error: unknown) {
            setLoading((prev) => !prev);
            if (error instanceof AxiosError) {
                const apiErrorResponse = error.response?.data as Errors;
                login(null);
                setMessage({
                    error: true,
                    msg: error.message,
                    errors: apiErrorResponse,
                });
                console.error(error);
            }
        } finally {
            setLoading(false);
        }
    };

    const handleRefresh = async () => {
        try {
            if (refreshToken) {
                setLoading((prev) => !prev);
                closeToast();

                const response = await refreshTokenService<{ access: string }>(
                    refreshToken,
                );

                setRefreshToken(null);
                login(response.access, true);
            }
        } catch (error) {
            if (error instanceof AxiosError) {
                const apiErrorResponse = error.response?.data as Errors;

                setMessage({
                    error: true,
                    msg: apiErrorResponse
                        ? apiErrorResponse?.errors?.[0]?.detail
                        : error.message,
                });
                console.error(error);
            }
        } finally {
            setLoading((prev) => !prev);
        }
    };

    useEffect(() => {
        if (refresh) {
            showModal("refresh");
        } else if (refresh === false) {
            closeToast();
            setMessage({ error: true, msg: "No refresh token found" });
        }
    }, [refresh]);

    return (
        <>
            {typeof message.error === "boolean" &&
                message.error !== undefined && (
                    <Toast
                        error={message.error}
                        msg={
                            !message.errors
                                ? message.msg
                                : message.errors.errors?.[0].code === "blank"
                                  ? "Fields may not be blank."
                                  : message.errors.errors?.[0].detail?? message.msg
                        }
                    />
                )}
            {refresh && (
                <Modal
                    close={true}
                    setModalState={undefined}
                    modalId={"refresh"}
                >
                    <h3 className="font-bold text-2xl">Hello!</h3>
                    <h5 className="font-light text-lg">
                        Your token has expired
                    </h5>
                    <p className="py-4 text-xl">
                        Would you like to extend your session ?
                    </p>
                    <div className="flex mt-4 justify-center">
                        <button
                            className="btn btn-success ml-6"
                            onClick={() => handleRefresh()}
                        >
                            {loading && (
                                <div
                                    className="inline-block h-6 w-6 mx-2 animate-spin rounded-full border-4 
                                    border-solid border-current border-e-transparent align-[-0.125em] 
                                    text-secondary motion-reduce:animate-[spin_1.5s_linear_infinite]"
                                    role="status"
                                ></div>
                            )}
                            Extend session
                        </button>
                    </div>
                </Modal>
            )}
            <div
                className="flex flex-col w-full max-w-md px-4 py-8 self-center my-auto rounded-lg 
            shadow bg-base-200 sm:px-6 md:px-8 lg:px-10"
            >
                {/* <div className="self-center mb-6 text-xl font-bold sm:text-2xl ">
                    Login
                </div> */}
                <img src={osupng} alt="parallel_gamit" />
                <div className="mt-8">
                    <form action="#" autoComplete="off" onSubmit={handleLogin}>
                        <div className="flex flex-col mb-2">
                            <div className="flex relative ">
                                <span
                                    className="rounded-l-md inline-flex  items-center px-3 border-t 
                                bg-white border-l border-b  border-gray-300 text-gray-500 shadow-sm text-sm"
                                >
                                    <svg
                                        xmlns="http://www.w3.org/2000/svg"
                                        fill="currentColor"
                                        viewBox="0 0 24 24"
                                        strokeWidth="1.5"
                                        width="15"
                                        height="15"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"
                                        />
                                    </svg>
                                </span>
                                {message.errors?.errors?.find(
                                    (e) => e.attr === "username",
                                ) && (
                                    <ExclamationCircleIcon
                                        title={
                                            message.errors?.errors?.find(
                                                (e) => e.attr === "username",
                                            )?.detail
                                        }
                                        className="size-6 text-red-600 absolute right-0 top-2 mr-2"
                                    />
                                )}
                                <input
                                    type="text"
                                    id="username"
                                    value={username}
                                    onChange={(e) =>
                                        setUsername(e.target.value)
                                    }
                                    className=" rounded-r-lg flex-1 appearance-none border border-gray-300 
                                    w-full py-2 px-4 bg-white text-gray-700 placeholder-gray-400 
                                    shadow-sm text-base focus:outline-none focus:ring-1 focus:ring-gray-400 
                                    focus:border-transparent"
                                    placeholder="Your username"
                                />
                            </div>
                        </div>
                        <div className="flex flex-col mb-6 ">
                            <div className="flex relative  ">
                                <span
                                    className="rounded-l-md inline-flex  items-center px-3 border-t bg-white 
                                border-l border-b  border-gray-300 text-gray-500 shadow-sm text-sm"
                                >
                                    <svg
                                        width="15"
                                        height="15"
                                        fill="currentColor"
                                        viewBox="0 0 1792 1792"
                                        xmlns="http://www.w3.org/2000/svg"
                                    >
                                        <path d="M1376 768q40 0 68 28t28 68v576q0 40-28 68t-68 28h-960q-40 0-68-28t-28-68v-576q0-40 28-68t68-28h32v-320q0-185 131.5-316.5t316.5-131.5 316.5 131.5 131.5 316.5q0 26-19 45t-45 19h-64q-26 0-45-19t-19-45q0-106-75-181t-181-75-181 75-75 181v320h736z"></path>
                                    </svg>
                                </span>
                                <input
                                    type="password"
                                    id="password"
                                    value={password}
                                    onChange={(e) =>
                                        setPassword(e.target.value)
                                    }
                                    className=" rounded-r-lg flex-1 appearance-none border
                                     border-gray-300 w-full py-2 px-4 bg-white 
                                     text-gray-700 placeholder-gray-400 shadow-sm 
                                     text-base focus:outline-none focus:ring-1 focus:ring-gray-400
                                      focus:border-transparent"
                                    placeholder="Your password"
                                />
                                {message.errors?.errors?.find(
                                    (e) => e.attr === "password",
                                ) && (
                                    <ExclamationCircleIcon
                                        title={
                                            message.errors?.errors?.find(
                                                (e) => e.attr === "password",
                                            )?.detail
                                        }
                                        className="size-6 text-red-600 absolute right-0 top-2 mr-2"
                                    />
                                )}
                            </div>
                        </div>
                        {/* <div className="flex items-center mb-6 -mt-4">
                            <div className="flex ml-auto">
                                <a
                                    href="#"
                                    className="inline-flex text-xs font-thin sm:text-sm text-gray-100 
                                    hover:text-white"
                                >
                                    Forgot Your Password?
                                </a>
                            </div>
                        </div> */}
                        <div className="flex w-full">
                            <button
                                type="submit"
                                disabled={loading}
                                className="flex justify-center py-2 px-4 disabled:opacity-50 
                                disabled:hover:bg-base-content bg-base-content hover:bg-opacity-85 
                                focus:ring-gray-400 focus:ring-offset-gray-200 text-white 
                                w-full transition ease-in duration-200 text-center text-base font-semibold 
                                shadow-md focus:outline-none focus:ring-2 focus:ring-offset-2  rounded-lg "
                            >
                                {loading && (
                                    <div
                                        className="inline-block h-6 w-6 mx-2 animate-spin rounded-full border-4 
                                        border-solid border-current border-e-transparent align-[-0.125em] 
                                        text-secondary motion-reduce:animate-[spin_1.5s_linear_infinite]"
                                        role="status"
                                    ></div>
                                )}
                                Login
                            </button>
                        </div>
                    </form>
                </div>
                {/* <div className="flex items-center justify-center mt-6">
                    <a
                        href="#"
                        target="_blank"
                        className="inline-flex items-center text-xs font-thin text-center text-gray-100 
                        hover:text-white"
                    >
                        <span className="ml-2">
                            You don&#x27;t have an account?
                        </span>
                    </a>
                </div> */}
            </div>
        </>
    );
};

export default Login;
