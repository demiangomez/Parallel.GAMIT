import { useFormReducer } from "@hooks/index";
import { FileErrors } from "@types";
import { useEffect } from "react";

interface FileDetailsProps {
    file: { id: string; name?: string };
    files: { file: File; description: string; id: number; name?: string }[];
    fileType: string;
    pageRecord: Record<string, string | number>;
    fileResults?: { id: number; errors: FileErrors | undefined }[];
    setFiles: React.Dispatch<
        React.SetStateAction<
            { file: File; description: string; id: number; name?: string }[]
        >
    >;
}

const FileDetails = ({
    file,
    files,
    fileType,
    pageRecord,
    fileResults,
    setFiles,
}: FileDetailsProps) => {
    const { id, pageType } = pageRecord;

    const { formState, dispatch } = useFormReducer<
        Record<string, string | number>
    >({
        filename: "",
        description: "",
        [pageType]: id ?? undefined,
    });

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;

        if (name === "name") {
            dispatch({
                type: "change_value",
                payload: {
                    inputName: "filename",
                    inputValue: value,
                },
            });

            setFiles((prev) => {
                const f = prev.find((f) => String(f.id) === file.id);

                if (f) {
                    return prev.map((p) =>
                        String(p.id) === file.id
                            ? {
                                  file: new File([p.file], value, {
                                      type: p.file.type,
                                  }),
                                  description: p.description,
                                  id: p.id,
                                  name: value,
                              }
                            : p,
                    );
                }
                return prev;
            });
        } else {
            dispatch({
                type: "change_value",
                payload: {
                    inputName: name,
                    inputValue: value,
                },
            });

            setFiles((prev) => {
                const f = prev.find((f) => String(f.id) === file.id);

                if (f) {
                    return prev.map((p) =>
                        String(p.id) === file.id
                            ? {
                                  file: p.file,
                                  description: value,
                                  id: p.id,
                                  name: p.name,
                              }
                            : p,
                    );
                }
                return prev;
            });
        }
    };

    useEffect(() => {
        if (files) {
            const f = files.find((f) => String(f.id) === file.id);
            dispatch({
                type: "set",
                payload: {
                    filename: f?.name ? f.name : (f?.file.name ?? ""),
                    description: f?.description ?? "",
                    [pageType]: id ?? undefined,
                },
            });
        }
    }, [files]);

    const nameInputsToDisable = ["gnss", "other"];

    const errorMessages = fileResults?.reduce(
        (acc, curr) => {
            acc[curr.id] = curr.errors;
            return acc;
        },
        {} as Record<number, FileErrors | undefined>,
    );

    const errorMessageKey = errorMessages
        ? Object.keys(errorMessages?.[Number(file.id)] ?? {})[0]
        : undefined; // [0] bcs it return just the first file who returned an error

    const typeError =
        errorMessages && errorMessageKey
            ? Object.keys(
                  errorMessages?.[Number(file.id)]?.[
                      errorMessageKey as keyof FileErrors
                  ] as any,
              )[0]
            : undefined;

    return (
        <div
            className="flex flex-col items-center border-neutral-200 border-2 rounded-lg py-2 shadow-md"
            key={file.id}
        >
            <div className="w-10/12">
                <label className="label font-bold">FILE NAME</label>
                <label
                    className={`w-full input input-bordered flex items-center gap-2 
                        ${typeError ? (typeError !== "success" ? "input-error" : "input-success") : ""}
                    `}
                    title={formState["filename"] as string}
                >
                    <input
                        type="text"
                        value={formState["filename"]}
                        readOnly={nameInputsToDisable.includes(fileType)}
                        name="name"
                        onChange={handleChange}
                        className="w-full truncate"
                        autoComplete="off"
                    />
                </label>
            </div>
            <div className="w-10/12">
                <label className="label font-bold">DESCRIPTION</label>
                <label
                    className={`w-full input input-bordered flex items-center gap-2  ${errorMessages?.[Number(file.id)]?.["description" as keyof FileErrors] ? "input-error" : ""}`}
                    title={formState["description"] as string}
                >
                    <input
                        type="text"
                        className="w-full"
                        value={formState["description"]}
                        onChange={handleChange}
                        name="description"
                        autoComplete="off"
                    />
                </label>
            </div>
        </div>
    );
};

export default FileDetails;
