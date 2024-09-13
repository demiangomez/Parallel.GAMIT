import { Errors } from "@types";

interface AlertProps {
    msg: { status: number; msg: string; errors?: Errors } | undefined;
}

const Alert = ({ msg }: AlertProps) => {
    const errorDetail = msg?.errors?.errors?.[0]?.detail;

    return (
        <>
            {msg && (
                <div
                    role="alert"
                    className={`alert ${msg && "errors" in msg ? "alert-error" : "alert-success"}`}
                >
                    {"errors" in msg ? (
                        <>
                            <svg
                                xmlns="http://www.w3.org/2000/svg"
                                className="stroke-current shrink-0 h-6 w-6"
                                fill="none"
                                viewBox="0 0 24 24"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth="2"
                                    d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
                                />
                            </svg>
                            <div className="flex flex-col text-xl">
                                <span>
                                    {(
                                        msg?.msg?.charAt(0).toUpperCase() +
                                        msg?.msg?.slice(1)
                                    )?.replace("_", " ")}
                                </span>
                                <span className="font-light text-sm">
                                    {errorDetail && `${errorDetail}`}
                                </span>
                            </div>
                        </>
                    ) : (
                        <>
                            <svg
                                xmlns="http://www.w3.org/2000/svg"
                                className="stroke-current shrink-0 h-6 w-6"
                                fill="none"
                                viewBox="0 0 24 24"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth="2"
                                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                                />
                            </svg>
                            <span>{msg.msg}</span>
                        </>
                    )}
                </div>
            )}
        </>
    );
};

export default Alert;
