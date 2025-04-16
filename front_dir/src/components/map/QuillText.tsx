import { useEffect, useRef } from "react";

import ReactQuill from "react-quill";

import "react-quill/dist/quill.snow.css";

interface QuillTextProps {
    value: string;
    setValue: (value: string) => void;
    clase: string;
}

const QuillText = ({ value, setValue, clase }: QuillTextProps) => {
    const quillRef = useRef<ReactQuill>(null);
    const toolBarOptions = [
        ["bold", "italic", "strike"],
        ["code-block"],
        [{ list: "ordered" }, { list: "bullet" }],
        ["blockquote"],
        [{ size: ["small", false, "large", "huge"] }],
    ];

    useEffect(() => {
        if (quillRef.current) {
            // Set default font size to large, the same size than text-2xl tailwind class
            const editor = quillRef.current.getEditor();
            editor.format("size", "large");

            // Set editor cursor to end of text
            const length = editor.getLength();
            editor.setSelection(length, 0);
        }
    }, []);

    const modules = {
        toolbar: toolBarOptions,
    };

    useEffect(() => {
        const toolbar = document.querySelector(".ql-toolbar");
        if (toolbar) {
            toolbar.addEventListener("mousedown", (e) => {
                e.preventDefault();
            });
            (toolbar as HTMLElement).style.userSelect = "none"; // Add this line to prevent text selection
        }
    }, []);

    return (
        <ReactQuill
            ref={quillRef}
            theme="snow"
            value={value}
            onChange={setValue}
            modules={modules}
            className={clase}
            style={{
                direction: "ltr",
                textAlign: "left",
            }}
        />
    );
};

export default QuillText;
