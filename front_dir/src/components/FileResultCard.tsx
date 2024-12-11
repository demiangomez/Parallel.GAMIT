import {
    CheckIcon,
    ExclamationTriangleIcon,
} from "@heroicons/react/24/outline";

import { FileErrors } from "@types";

interface Props {
    fileResults: {
        id: number;
        errors: FileErrors | undefined;
    }[];
}

const FileResultCard = ({ fileResults }: Props) => {
    return (
        <>
            {fileResults.length > 0 && (
                <div className="w-full">
                    <label className="label font-bold">RESULT</label>
                    <div className="w-full grid grid-cols-3 gap-2 grid-flow-dense mt-6 max-h-72 overflow-y-auto p-2">
                        {fileResults.map((result) => (
                            <div
                                key={result.id}
                                className="w-full h-full border-neutral-200 border-2 rounded-lg"
                            >
                                {result.errors &&
                                    Object.entries(result.errors).map(
                                        ([key, err]) => {
                                            const valueKey =
                                                Object.keys(err)[0];
                                            const value = err[valueKey][0];

                                            return (
                                                <div
                                                    key={key}
                                                    className="flex items-center shadow-xl p-2 rounded-lg w-full h-full break-words overflow-hidden"
                                                >
                                                    {valueKey !== "success" ? (
                                                        <div className="w-6 mr-2">
                                                            <ExclamationTriangleIcon className="size-6 text-yellow-600" />
                                                        </div>
                                                    ) : (
                                                        <div className="w-6 mr-2">
                                                            <CheckIcon className="h-6 w-6 text-green-600 mr-2" />
                                                        </div>
                                                    )}
                                                    <div className="flex flex-col my-2 break-words">
                                                        <span className="font-semibold">
                                                            {key === "undefined"
                                                                ? "Error"
                                                                : key}
                                                        </span>
                                                        <span
                                                            className={`${
                                                                valueKey !==
                                                                "success"
                                                                    ? "text-error"
                                                                    : "text-green-800 opacity-80"
                                                            }`}
                                                        >
                                                            {key ===
                                                                "undefined" ||
                                                            valueKey === "0"
                                                                ? Array.isArray(
                                                                      err[
                                                                          valueKey
                                                                      ],
                                                                  )
                                                                    ? err[
                                                                          valueKey
                                                                      ][0]
                                                                    : err
                                                                : value}
                                                        </span>
                                                    </div>
                                                </div>
                                            );
                                        },
                                    )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </>
    );
};

export default FileResultCard;
