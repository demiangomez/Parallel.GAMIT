import { Modal } from "@componentsReact";
import { pdfjs } from "react-pdf";
import { Document, Page } from "react-pdf";

import pdfJSWorkerURL from "pdfjs-dist/build/pdf.worker?url";

import { ArrowDownTrayIcon } from "@heroicons/react/24/outline";

import { useCallback, useState } from "react";

import useResizeObserver from "@hooks/useResizeObserver";

import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = pdfJSWorkerURL;

interface Props {
    file: string | undefined;
    filename: string | undefined;
    closeModal: () => void;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
}

const RenderFileModal = ({
    file,
    filename,
    closeModal,
    setStateModal,
}: Props) => {
    const resizeObserverOptions = {};

    const [numPages, setNumPages] = useState<number>();

    const [containerRef, setContainerRef] = useState<HTMLElement | null>(null);
    const [containerWidth, setContainerWidth] = useState<number>();

    const onResize = useCallback<ResizeObserverCallback>((entries) => {
        const [entry] = entries;

        if (entry) {
            setContainerWidth(entry.contentRect.width);
        }
    }, []);

    useResizeObserver(containerRef, resizeObserverOptions, onResize);

    function onDocumentLoadSuccess({ numPages: nextNumPages }: any): void {
        setNumPages(nextNumPages);
    }

    const handleCloseModal = () => {
        closeModal();
    };

    return (
        <Modal
            close={false}
            modalId={"FileRender"}
            size={"smPlus"}
            handleCloseModal={() => handleCloseModal()}
            setModalState={setStateModal}
        >
            <div className="flex flex-col items-center">
                <div
                    className="w-full max-w-[calc(100%-2em)] m-4 flex flex-col items-center justify-center"
                    ref={setContainerRef}
                >
                    <div className="mb-6 flex justify-center items-center">
                        <a
                            className="btn-circle btn-ghost flex justify-center"
                            download={filename}
                            href={file}
                        >
                            <ArrowDownTrayIcon className="size-6 self-center" />
                        </a>
                    </div>
                    <Document file={file} onLoadSuccess={onDocumentLoadSuccess}>
                        {Array.from(new Array(numPages), (_el, index) => {
                            return (
                                <Page
                                    key={`page_${index + 1}`}
                                    pageNumber={index + 1}
                                    width={
                                        containerWidth
                                            ? Math.min(containerWidth, 800)
                                            : 800
                                    }
                                >
                                    <div
                                        style={{
                                            display: "flex",
                                            justifyContent: "center",
                                            marginBottom: "1rem",
                                        }}
                                    >
                                        <span className="text-gray-600 font-thin text-sm">
                                            page {index + 1}
                                        </span>
                                    </div>
                                </Page>
                            );
                        })}
                    </Document>
                </div>
            </div>
        </Modal>
    );
};

export default RenderFileModal;
