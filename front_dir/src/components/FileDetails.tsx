import { useFormReducer } from "@hooks/index";
import { FileErrors } from "@types";
import { useEffect } from "react";

interface FileDetailsProps {
    file: { id: string; name?: string };
    files: { file: File; description: string; id: number; name?: string }[];
    fileType: string;
    pageRecord: Record<string, string | number>;
    msg?:
        | {
              status: number;
              msg: string;
              errors?: FileErrors;
          }
        | undefined;
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
    msg,
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

    const errorMessages =
        msg?.errors && "error_message" in msg.errors
            ? msg.errors.error_message
            : undefined;

    const errorMessageKey = Object.keys(
        errorMessages?.[(file?.name as any) ?? Number(file.id)] ?? {},
    )[0]; // [0] bcs it return just the first file who returned an error

    return (
        <div
            className="flex flex-col items-center space-y-3 border-neutral-200 border-2</div> rounded-lg p-2 shadow-md"
            key={file.id}
        >
            <div className="w-2/4">
                <label className="label font-bold">FILE NAME</label>
                <label
                    className={`w-full input input-bordered flex items-center gap-2 
                        ${errorMessages?.[(file?.name as any) ?? Number(file.id)]?.[errorMessageKey] ? "input-error" : ""}
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
            <div className="w-2/4">
                <label className="label font-bold">DESCRIPTION</label>
                <label
                    className={`w-full input input-bordered flex items-center gap-2  ${errorMessages?.[Number(file.id)]?.["description"] ? "input-error" : ""}`}
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
