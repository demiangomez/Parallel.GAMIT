import { ExclamationTriangleIcon } from "@heroicons/react/24/outline";
import { Errors, RinexFileResponse } from "@types";
interface AlertProps {
    msg:
        | {
              status: number;
              msg: string;
              errors?: Errors | RinexFileResponse;
              rinex_other_errors?: { [key: string]: string[] };
          }
        | undefined;
}

const Alert = ({ msg }: AlertProps) => {
    const errorDetail =
        msg?.errors && "errors" in msg.errors
            ? msg.errors.errors?.[0]?.detail
            : undefined;

    const rinexErrorMessages =
        msg?.errors && "error_message" in msg.errors
            ? msg.errors.error_message
            : undefined;

    const extractedErrorMessages = rinexErrorMessages
        ? Object.values(rinexErrorMessages).flat()
        : [];

    return (
        <div className="flex flex-col w-full">
            {msg && (
                <div
                    role="alert"
                    className={`alert ${msg && "errors" in msg ? "alert-error" : msg.status === 199 ? "alert-warning" : "alert-success"}`}
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
                                    {errorDetail
                                        ? `${errorDetail}`
                                        : extractedErrorMessages}
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
                            <span className="">
                                {msg.msg && msg.msg.includes("\n")
                                    ? msg.msg.split("\n").map((l, idx) => (
                                          <ul
                                              key={idx + l}
                                              className="list-disc ml-3"
                                          >
                                              <li
                                                  className={
                                                      idx === 0
                                                          ? "font-bold list-none -ml-4"
                                                          : "ml-4"
                                                  }
                                              >
                                                  {l}
                                              </li>
                                          </ul>
                                      ))
                                    : msg.msg}
                            </span>
                        </>
                    )}
                </div>
            )}
            {msg?.rinex_other_errors && (
                <div
                    role="alert"
                    className="alert alert-warning font-light text-sm mt-4"
                >
                    <ExclamationTriangleIcon className="size-6" />
                    <div className="flex flex-col">
                        <span className="label-text">other stations</span>
                        {Object.entries(msg.rinex_other_errors).map(
                            ([key, value]) => (
                                <span key={key}>
                                    <strong className="text-base">
                                        {(
                                            key.charAt(0).toUpperCase() +
                                            key.slice(1)
                                        )
                                            .replace("_", " ")
                                            .replace("_", " ")}
                                    </strong>
                                    : {value}
                                </span>
                            ),
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default Alert;
