import { useEffect, useMemo, useState } from "react";
import { Modal, Spinner } from "@componentsReact";

import { useAuth, useApi } from "@hooks";
import {
    getStationImageByIdService,
    getStationVisitsImagesByIdService,
} from "@services";

import { StationImagesData } from "@types";

type Photo = {
    id: number;
    actual_image: string;
    description: string;
    name: string;
};

interface Props {
    photo: Photo | undefined;
    visit?: boolean;
    closeModal: () => void;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
}

const ImageModal = ({ photo, visit, closeModal, setStateModal }: Props) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [loading, setLoading] = useState<boolean>(false);

    const [originalPhoto, setOriginalPhoto] = useState<
        StationImagesData | undefined
    >(undefined);

    const handleCloseModal = () => {
        closeModal();
    };

    const getOriginalPhoto = async () => {
        try {
            setLoading(true);

            const service = visit
                ? getStationVisitsImagesByIdService
                : getStationImageByIdService;

            const res = await service<StationImagesData>(api, photo?.id ?? 0);

            if (res.actual_image) {
                setOriginalPhoto(res);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        getOriginalPhoto();
    }, [photo]);

    const image = useMemo(() => {
        return (
            <Modal
                close={false}
                modalId={"ViewStationPhoto"}
                size={"md"}
                handleCloseModal={() => handleCloseModal()}
                setModalState={setStateModal}
            >
                {loading && (
                    <div className="flex flex-col items-center justify-center space-y-4 w-full">
                        <span className="font-bold text-lg">
                            Loading image, please wait ...
                        </span>
                        <Spinner size="lg" />
                    </div>
                )}
                {originalPhoto?.name && (
                    <div className="space-y-4">
                        <img
                            className="w-full h-fit object-contain"
                            src={
                                "data:image/png;base64," +
                                originalPhoto?.actual_image
                            }
                            alt={"photo" + originalPhoto?.name}
                        />
                        {originalPhoto?.description && (
                            <p className="break-words border-t-2 border-neutral-300 pt-3 leading-6 tracking-tight text-xl font-semibold">
                                {originalPhoto?.description}
                            </p>
                        )}
                    </div>
                )}
            </Modal>
        );
    }, [originalPhoto, loading]);
    return image;
};

export default ImageModal;
