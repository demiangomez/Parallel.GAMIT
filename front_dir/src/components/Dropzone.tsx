import { useEffect} from "react";
import { useDropzone } from "react-dropzone";
import { CloudArrowDownIcon } from "@heroicons/react/24/outline";

interface DropzoneProps {
    file: File | undefined;
    setFile: React.Dispatch<React.SetStateAction<File | undefined>>;
}

const Dropzone = ({ file, setFile }: DropzoneProps) => {
    const { acceptedFiles, getRootProps, getInputProps } = useDropzone({
        maxFiles: 1,
    });

    useEffect(() => {
        if (acceptedFiles.length > 0) {
            setFile(acceptedFiles[0]);
        }
    }, [acceptedFiles, setFile]);

    return (
        <section className="w-full p-2">
            <div
                {...getRootProps({
                    className:
                        "w-full border-2 border-dashed cursor-pointer border-neutral-400 rounded-lg p-4 focus:border-violet-500 text-neutral-500",
                    style: {
                        flex: 1,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        padding: "20px",
                        backgroundColor: "#fafafa",
                        outline: "none",
                        transition: "border .24s ease-in-out",
                    },
                })}
            >
                <input {...getInputProps()} />
                {file ? (
                    <div>
                        <p>{file.name}</p>
                        <p>{file.size} bytes</p>
                    </div>
                ) : (
                    <>
                        <CloudArrowDownIcon className="size-10" />
                        <p>
                            Drag 'n' drop station info file, or click to select
                            file
                        </p>
                    </>
                )}
            </div>
        </section>
    );
};

export default Dropzone;