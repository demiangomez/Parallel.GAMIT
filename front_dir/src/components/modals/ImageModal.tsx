import { Modal } from "@componentsReact";
import { useMemo } from "react";

type Photo = {
    id: number;
    actual_image: string;
    description: string;
    name: string;
};

interface Props {
    photo: Photo | undefined;
    closeModal: () => void;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
}

const ImageModal = ({ photo, closeModal, setStateModal }: Props) => {
    const handleCloseModal = () => {
        closeModal();
    };

    const image = useMemo(() => {
        if (!photo) return null;
        return (
            <Modal
                close={false}
                modalId={"ViewStationPhoto"}
                size={"md"}
                handleCloseModal={() => handleCloseModal()}
                setModalState={setStateModal}
            >
                <div className="space-y-4">
                    <img
                        className="w-full h-fit object-contain"
                        src={"data:image/png;base64," + photo?.actual_image}
                        alt={"photo"}
                    />
                    {photo.description && (
                        <p className="break-words border-t-2 border-neutral-300 pt-3 leading-6 tracking-tight text-xl font-semibold">
                            {photo.description}
                        </p>
                    )}
                </div>
            </Modal>
        );
    }, [photo]);
    return image;
};

export default ImageModal;
