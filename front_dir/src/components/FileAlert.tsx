import { FileErrors } from "@types";

interface AlertProps {
    msg:
        | {
              status: number;
              msg: string;
              errors?: FileErrors;
          }
        | undefined;
}

const FileAlert = ({ msg }: AlertProps) => {
    const errorMessages =
        msg?.errors && "error_message" in msg.errors
            ? msg.errors.error_message
            : undefined;

    // const errorMessagesKeys = errorMessages
    //     ? Object.keys(errorMessages).flatMap((key) =>
    //           Object.keys(errorMessages[key as any]),
    //       )
    //     : [];
    return (
        <div className="flex flex-col w-full">
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
                                <span className="font-bold">
                                    {(
                                        msg?.msg?.charAt(0).toUpperCase() +
                                        msg?.msg?.slice(1)
                                    )?.replace("_", " ")}
                                </span>
                                {Object.keys(errorMessages || {}).map((key) => {
                                    const error = errorMessages?.[key as any];
                                    if (typeof error === "string") {
                                        return (
                                            <div
                                                key={key}
                                                className="flex flex-col"
                                            >
                                                <span className="text-base font-semibold">
                                                    ERROR
                                                </span>
                                                <span className="font-light text-sm">
                                                    {error}
                                                </span>
                                            </div>
                                        );
                                    } else if (typeof error === "object") {
                                        return Object.keys(error).map(
                                            (subKey) => (
                                                <div
                                                    key={subKey}
                                                    className="flex flex-col"
                                                >
                                                    <span className="text-base font-semibold">
                                                        {subKey.toUpperCase()}
                                                    </span>
                                                    {Array.isArray(
                                                        error[subKey],
                                                    ) ? (
                                                        error[subKey].map(
                                                            (
                                                                msg: string,
                                                                idx: number,
                                                            ) => (
                                                                <span
                                                                    key={idx}
                                                                    className="font-light text-sm"
                                                                >
                                                                    {msg}
                                                                </span>
                                                            ),
                                                        )
                                                    ) : (
                                                        <span className="font-light text-sm">
                                                            {error[subKey]}
                                                        </span>
                                                    )}
                                                </div>
                                            ),
                                        );
                                    } else {
                                        return null;
                                    }
                                })}
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
        </div>
    );
};

export default FileAlert;
