import { useEffect, useState } from "react";
import {
    AddFileModal,
    Alert,
    ConfirmDeleteModal,
    ImageModal,
    Modal,
    VisitCampaignModal,
    VisitPeopleModal,
} from "@componentsReact";

import Slider from "react-slick";

import "slick-carousel/slick/slick.css";
import "slick-carousel/slick/slick-theme.css";

import "@assets/slickCustom.css";

import useApi from "@hooks/useApi";
import { useAuth } from "@hooks/useAuth";

import defPhoto from "@assets/images/placeholder.png";

import {
    ArrowDownTrayIcon,
    PencilSquareIcon,
    PlusCircleIcon,
    TrashIcon,
} from "@heroicons/react/24/outline";

import {
    delStationVisitFilesService,
    delStationVisitGnssFilesService,
    delStationVisitsImagesService,
    getPeopleService,
    getStationVisitFilesService,
    getStationVisitGnssFilesService,
    getStationVisitsByIdService,
    getStationVisitsImagesService,
    patchStationVisitService,
} from "@services";

import {
    People as PeopleType,
    PeopleServiceData,
    StationVisitsData,
    StationVisitsFilesData,
    StationVisitsFilesServiceData,
    Errors,
    ErrorResponse,
    StationCampaignsData,
} from "@types";

import { showModal } from "@utils";
import { useFormReducer } from "@hooks/index";

interface Props {
    campaigns: StationCampaignsData[] | undefined;
    visitId: number | undefined;
    closeModal: () => void;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
}

const StationVisitDetailModal = ({
    campaigns,
    visitId,
    closeModal,
    setStateModal,
}: Props) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const [fileMsg, setFileMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [peopleMsg, setPeopleMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [commentsMsg, setCommentsMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    // Visit photo

    const [blurPhoto, setBlurPhoto] = useState<
        { blur: boolean; id: number } | undefined
    >(undefined);

    const [delPhoto, setDelPhoto] = useState<
        StationVisitsFilesData | undefined
    >(undefined);

    const [photo, setPhoto] = useState<Photo | undefined>(undefined);

    // ---

    const [loading, setLoading] = useState<boolean>(false);

    const [commentLoading, setCommentLoading] = useState<boolean>(false);

    const [edit, setEdit] = useState<boolean>(false);

    const [visit, setVisit] = useState<StationVisitsData | undefined>(
        undefined,
    );

    const [images, setImages] = useState<StationVisitsFilesData[] | undefined>(
        undefined,
    );

    const [people, setPeople] = useState<PeopleType[]>([]);

    const [files, setFiles] = useState<StationVisitsFilesData[] | undefined>(
        undefined,
    );

    const [gnssFiles, setGnssFiles] = useState<
        StationVisitsFilesData[] | undefined
    >(undefined);

    const [fileType, setFileType] = useState<string | undefined>(undefined);

    const [fileToDel, setFileToDel] = useState<number | undefined>(undefined);

    const [personToDel, setPersonToDel] = useState<number | undefined>(
        undefined,
    );

    const visitCampaign = campaigns?.find(
        (c) => c.id === Number(visit?.campaign),
    );

    type Photo = {
        id: number;
        actual_image: string;
        description: string;
        name: string;
    };

    type expandedStationVisitData = StationVisitsData & {
        statusCode: number;
    };

    const { formState, dispatch } = useFormReducer({
        comments: "",
    });

    const getVisitById = async () => {
        try {
            if (!visitId) return null;
            setLoading(true);
            const res =
                await getStationVisitsByIdService<expandedStationVisitData>(
                    api,
                    visitId,
                );
            if (res.statusCode === 200) {
                setVisit(res);
            }
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const getVisitImagesById = async () => {
        try {
            if (!visitId) return null;
            setLoading(true);
            const res =
                await getStationVisitsImagesService<StationVisitsFilesServiceData>(
                    api,
                    {
                        limit: 0,
                        offset: 0,
                        visit_api_id: String(visitId),
                    },
                );
            if (res.statusCode === 200) {
                setImages(res.data);
            }
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const getVisitsAttachedFiles = async () => {
        try {
            if (!visitId) return null;
            setLoading(true);
            const res =
                await getStationVisitFilesService<StationVisitsFilesServiceData>(
                    api,
                    {
                        limit: 0,
                        offset: 0,
                        visit_api_id: String(visitId),
                    },
                );

            if (res.statusCode === 200) {
                setFiles(res.data);
            }
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const delVisitAttachedFile = async () => {
        try {
            if (!fileToDel) return null;

            setLoading(true);
            const res = await delStationVisitFilesService<ErrorResponse>(
                api,
                fileToDel,
            );
            if ("status" in res && res.status === "success") {
                setFileMsg({
                    status: res.statusCode,
                    msg: res.msg,
                });
            } else {
                setFileMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const getVisitsGnssFiles = async () => {
        try {
            if (!visitId) return null;
            setLoading(true);
            const res =
                await getStationVisitGnssFilesService<StationVisitsFilesServiceData>(
                    api,
                    {
                        limit: 0,
                        offset: 0,
                        visit_api_id: String(visitId),
                    },
                );
            if (res.statusCode === 200) {
                setGnssFiles(res.data);
            }
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const delVisitGnssFile = async () => {
        try {
            if (!fileToDel) return null;

            setLoading(true);
            const res = await delStationVisitGnssFilesService<ErrorResponse>(
                api,
                fileToDel,
            );
            if ("status" in res && res.status === "success") {
                setFileMsg({
                    status: res.statusCode,
                    msg: res.msg,
                });
            } else {
                setFileMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const getPeople = async () => {
        try {
            const res = await getPeopleService<PeopleServiceData>(api);
            setPeople(res.data);
        } catch (err) {
            console.error(err);
        }
    };

    const patchVisit = async () => {
        try {
            if (!visitId) return null;
            setCommentLoading(true);

            const formData = new FormData();

            Object.entries(formState).forEach(([key, value]) => {
                formData.append("station", String(visit?.station));
                formData.append("date", visit?.date ?? "");
                formData.append(key, value);
            });

            const res = await patchStationVisitService<ErrorResponse>(
                api,
                visitId,
                formData,
            );
            if ("status" in res) {
                setCommentsMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setCommentsMsg({
                    status: 200,
                    msg: "Comments updated successfully",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setCommentLoading(false);
            setTimeout(() => {
                setCommentsMsg(undefined);
            }, 2500);
        }
    };

    const delPeople = async () => {
        try {
            if (!visitId) return null;
            setLoading(true);

            const peopleToDel = visit?.people.find(
                (p: { id: number }) => p.id === personToDel,
            );

            if (!peopleToDel) return null;

            const rest = { ...visit };
            rest.people = rest.people.filter(
                (p: { id: number }) => p.id !== personToDel,
            );

            delete rest.log_sheet_actual_file;
            delete rest.log_sheet_filename;
            delete rest.navigation_actual_file;
            delete rest.navigation_filename;

            rest.campaign = rest.campaign ?? "";

            const formData = new FormData();

            Object.entries(rest).forEach(([key, value]) => {
                if (key === "people") {
                    value.forEach((p: { id: number; name: string }) => {
                        formData.append("people", String(p.id));
                    });
                } else {
                    formData.append(key, value);
                }
            });

            const res = await patchStationVisitService<ErrorResponse>(
                api,
                visitId,
                formData,
            );
            if ("status" in res) {
                setPeopleMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setPeopleMsg({
                    status: 200,
                    msg: "People Visit updated successfully",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const delCampaign = async () => {
        try {
            if (!visitId) return null;
            setLoading(true);

            const rest = { ...visit };
            rest.campaign = "";

            delete rest.log_sheet_actual_file;
            delete rest.log_sheet_filename;
            delete rest.navigation_actual_file;
            delete rest.navigation_filename;

            const formData = new FormData();

            Object.entries(rest).forEach(([key, value]) => {
                if (key === "people") {
                    value.forEach((p: { id: number; name: string }) => {
                        formData.append("people", String(p.id));
                    });
                } else {
                    formData.append(key, value);
                }
            });

            const res = await patchStationVisitService<ErrorResponse>(
                api,
                visitId,
                formData,
            );
            if ("status" in res) {
                setPeopleMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setPeopleMsg({
                    status: 200,
                    msg: "Campaign Visit updated successfully",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const delVisitFiles = async () => {
        try {
            if (!visitId) return null;
            setLoading(true);

            const rest = { ...visit };

            if (!rest.campaign) delete rest.campaign;

            delete rest.log_sheet_actual_file;
            delete rest.log_sheet_filename;
            delete rest.navigation_actual_file;
            delete rest.navigation_filename;

            const formData = new FormData();
            if (fileType === "logsheet") {
                formData.append("log_sheet_file_delete", "true");
            } else {
                formData.append("navigation_file_delete", "true");
            }

            Object.entries(rest).forEach(([key, value]) => {
                if (key === "people") {
                    value.forEach((p: { id: number; name: string }) => {
                        formData.append("people", String(p.id));
                    });
                } else {
                    formData.append(key, value);
                }
            });

            const res = await patchStationVisitService<ErrorResponse>(
                api,
                visitId,
                formData,
            );
            if ("status" in res) {
                setPeopleMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setPeopleMsg({
                    status: 200,
                    msg: "Visit files updated successfully",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const delVisitImage = async () => {
        try {
            if (!delPhoto) return null;

            setLoading(true);
            const res = await delStationVisitsImagesService<ErrorResponse>(
                api,
                delPhoto.id,
            );
            if ("status" in res && res.status === "success") {
                setFileMsg({
                    status: res.statusCode,
                    msg: res.msg,
                });
            } else {
                setFileMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleCloseModal = () => {
        closeModal();
    };

    const getAll = () => {
        getVisitById();
        getVisitImagesById();
        getVisitsAttachedFiles();
        getVisitsGnssFiles();
    };

    useEffect(() => {
        getPeople();
        getAll();
    }, [visitId]);

    useEffect(() => {
        dispatch({
            type: "change_value",
            payload: {
                inputName: "comments",
                inputValue: visit?.comments ?? "",
            },
        });
    }, [visit]);

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    const settings = {
        dots: true,
        infinite: true,
        speed: 500,
        slidesToShow: 1,
        slidesToScroll: 1,
    };

    const errorBadge = commentsMsg?.errors?.errors?.find(
        (error) => error.attr === "comments",
    );

    return (
        <Modal
            close={false}
            modalId={"VisitDetail"}
            size={"md"}
            handleCloseModal={() => handleCloseModal()}
            setModalState={setStateModal}
        >
            <div className="space-y-4">
                <div className="w-full inline-flex">
                    <h1 className="w-full flex justify-center mb-4 text-2xl font-bold">
                        {visit?.date}
                    </h1>

                    <button
                        className="flex items-center btn btn-ghost btn-circle"
                        onClick={() => setEdit(!edit)}
                    >
                        <PencilSquareIcon title="edit" className="size-8" />
                    </button>
                </div>
                <div className="grid grid-cols-2 grid-flow-dense">
                    <div className="card bg-base-200 grow shadow-xl mr-4">
                        <h2 className="card-title border-b-2 border-base-300 p-2">
                            General
                        </h2>

                        <div className="card-body">
                            <div className="grid grid-cols-1 gap-6">
                                <div className="flex items-center">
                                    <div className="flex flex-col w-full max-h-60 pr-2 overflow-auto">
                                        <span className="inline-flex items-end justify-between">
                                            <strong className="text-lg">
                                                Campaign:{" "}
                                            </strong>
                                            <button
                                                className="btn btn-ghost btn-circle ml-2"
                                                onClick={() => {
                                                    setModals({
                                                        show: true,
                                                        title: "AddVisitCampaign",
                                                        type: "add",
                                                    });
                                                }}
                                                disabled={
                                                    visit?.campaign
                                                        ? true
                                                        : false
                                                }
                                            >
                                                <PlusCircleIcon
                                                    strokeWidth={1.5}
                                                    stroke="currentColor"
                                                    className="w-8 h-10"
                                                />
                                            </button>
                                        </span>
                                        <div className="w-full grid grid-cols-1 grid-flow-dense">
                                            <div className="flex flex-col w-full rounded-md bg-neutral-content">
                                                {visit?.campaign ? (
                                                    <div
                                                        className={`flex-grow overflow-hidden ${!edit ? "p-2" : ""} last:border-b-0 border-b-2 border-neutral-200`}
                                                    >
                                                        <div className="p-1 flex w-full justify-between items-center">
                                                            <button
                                                                className="btn btn-ghost btn-circle mr-2"
                                                                style={{
                                                                    display:
                                                                        !edit
                                                                            ? "none"
                                                                            : "",
                                                                }}
                                                                onClick={() => {
                                                                    setModals({
                                                                        show: true,
                                                                        title: "ConfirmDelete",
                                                                        type: "edit",
                                                                    });
                                                                }}
                                                            >
                                                                <TrashIcon className="size-6 text-red-600" />
                                                            </button>
                                                            <div className="flex flex-col w-full text-pretty break-words max-w-full px-2">
                                                                <h2 className="font-semibold text-md">
                                                                    {visit?.campaign
                                                                        ? "(" +
                                                                          visitCampaign?.name +
                                                                          ")" +
                                                                          " " +
                                                                          visitCampaign?.start_date +
                                                                          " - " +
                                                                          visitCampaign?.end_date
                                                                        : "N/A"}
                                                                </h2>
                                                            </div>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <div className="text-center text-neutral text-xl font-bold w-full rounded-md bg-neutral-content p-6">
                                                        There is no campaign
                                                        registered
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex items-center">
                                    <div className="flex flex-col w-full max-h-60 pr-2 overflow-auto">
                                        <div className="inline-flex items-end justify-between">
                                            <strong className="text-lg">
                                                People:{" "}
                                            </strong>
                                            <button
                                                className="btn btn-ghost btn-circle ml-2"
                                                onClick={() => {
                                                    setModals({
                                                        show: true,
                                                        title: "AddVisitPeople",
                                                        type: "add",
                                                    });
                                                }}
                                            >
                                                <PlusCircleIcon
                                                    strokeWidth={1.5}
                                                    stroke="currentColor"
                                                    className="w-8 h-10"
                                                />
                                            </button>
                                        </div>
                                        <div className="w-full grid grid-cols-1 grid-flow-dense">
                                            <div className="flex flex-col w-full rounded-md bg-neutral-content">
                                                {visit?.people.length > 0 ? (
                                                    visit?.people.map(
                                                        (p: {
                                                            id: number;
                                                            name: string;
                                                        }) => {
                                                            return (
                                                                <div
                                                                    className={`flex-grow overflow-hidden ${!edit ? "p-2" : ""} last:border-b-0 border-b-2 border-neutral-200`}
                                                                    key={p.id}
                                                                >
                                                                    <div className="p-1 flex w-full justify-between items-center">
                                                                        <button
                                                                            className="btn btn-ghost btn-circle mr-2"
                                                                            style={{
                                                                                display:
                                                                                    !edit
                                                                                        ? "none"
                                                                                        : "",
                                                                            }}
                                                                            onClick={() => {
                                                                                setPersonToDel(
                                                                                    p.id,
                                                                                );
                                                                                setModals(
                                                                                    {
                                                                                        show: true,
                                                                                        title: "ConfirmDelete",
                                                                                        type: "edit",
                                                                                    },
                                                                                );
                                                                            }}
                                                                        >
                                                                            <TrashIcon className="size-6 text-red-600" />
                                                                        </button>
                                                                        <div className="flex flex-col w-full text-pretty break-words max-w-full px-2">
                                                                            <h2 className="font-semibold text-md">
                                                                                {p?.name?.toUpperCase()}
                                                                            </h2>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            );
                                                        },
                                                    )
                                                ) : (
                                                    <div className="text-center text-neutral text-xl font-bold w-full rounded-md bg-neutral-content p-6">
                                                        There is no people
                                                        registered
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex items-center">
                                    <div className="flex flex-col w-full max-h-60 pr-2 overflow-auto">
                                        <div className="inline-flex items-end justify-between">
                                            <strong className="text-lg">
                                                Log Sheet:{" "}
                                            </strong>
                                            <button
                                                className="btn btn-ghost btn-circle ml-2"
                                                onClick={() => {
                                                    setModals({
                                                        show: true,
                                                        title: "AddFile",
                                                        type: "add",
                                                    });
                                                    setFileType("logsheet");
                                                }}
                                                disabled={
                                                    visit?.log_sheet_actual_file
                                                        ? true
                                                        : false
                                                }
                                            >
                                                <PlusCircleIcon
                                                    strokeWidth={1.5}
                                                    stroke="currentColor"
                                                    className="w-8 h-10"
                                                />
                                            </button>
                                        </div>
                                        <div className="w-full grid grid-cols-1 grid-flow-dense">
                                            <div className="flex flex-col w-full rounded-md bg-neutral-content">
                                                {visit?.log_sheet_filename ? (
                                                    <div
                                                        className={`flex-grow overflow-hidden ${!edit ? "p-2" : ""} last:border-b-0 border-b-2 border-neutral-200`}
                                                    >
                                                        <div className="p-1 flex w-full justify-between items-center">
                                                            <button
                                                                className="btn btn-ghost btn-circle mr-2"
                                                                style={{
                                                                    display:
                                                                        !edit
                                                                            ? "none"
                                                                            : "",
                                                                }}
                                                                onClick={() => {
                                                                    setFileType(
                                                                        "logsheet",
                                                                    );

                                                                    setModals({
                                                                        show: true,
                                                                        title: "ConfirmDelete",
                                                                        type: "edit",
                                                                    });
                                                                }}
                                                            >
                                                                <TrashIcon className="size-6 text-red-600" />
                                                            </button>
                                                            <div className="flex w-full items-center justify-between text-pretty break-words max-w-full px-2">
                                                                <h2 className="font-semibold text-md">
                                                                    {/* {p?.name?.toUpperCase()} */}
                                                                    {visit?.log_sheet_filename
                                                                        ? visit.log_sheet_filename
                                                                        : "N/A"}
                                                                </h2>
                                                                <a
                                                                    className="btn-circle btn-ghost flex justify-center"
                                                                    download={
                                                                        visit.log_sheet_filename
                                                                    }
                                                                    href={`data:application/octet-stream;base64,${visit.log_sheet_actual_file}`}
                                                                >
                                                                    <ArrowDownTrayIcon className="size-6 self-center" />
                                                                </a>
                                                            </div>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <div className="text-center text-neutral text-xl font-bold w-full rounded-md bg-neutral-content p-6">
                                                        There is no log sheet
                                                        file
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex items-center">
                                    <div className="flex flex-col w-full max-h-60 pr-2 overflow-auto">
                                        <div className="inline-flex items-end justify-between">
                                            <strong className="text-lg">
                                                Navigation File:{" "}
                                            </strong>
                                            <button
                                                className="btn btn-ghost btn-circle ml-2"
                                                onClick={() => {
                                                    setModals({
                                                        show: true,
                                                        title: "AddFile",
                                                        type: "add",
                                                    });
                                                    setFileType("navfile");
                                                }}
                                                disabled={
                                                    visit?.navigation_actual_file
                                                        ? true
                                                        : false
                                                }
                                            >
                                                <PlusCircleIcon
                                                    strokeWidth={1.5}
                                                    stroke="currentColor"
                                                    className="w-8 h-10"
                                                />
                                            </button>
                                        </div>
                                        <div className="w-full grid grid-cols-1 grid-flow-dense">
                                            <div className="flex flex-col w-full rounded-md bg-neutral-content">
                                                {visit?.navigation_filename ? (
                                                    <div
                                                        className={`flex-grow overflow-hidden ${!edit ? "p-2" : ""} last:border-b-0 border-b-2 border-neutral-200`}
                                                    >
                                                        <div className="p-1 flex w-full justify-between items-center">
                                                            <button
                                                                className="btn btn-ghost btn-circle mr-2"
                                                                style={{
                                                                    display:
                                                                        !edit
                                                                            ? "none"
                                                                            : "",
                                                                }}
                                                                onClick={() => {
                                                                    setFileType(
                                                                        "navfile",
                                                                    );

                                                                    setModals({
                                                                        show: true,
                                                                        title: "ConfirmDelete",
                                                                        type: "edit",
                                                                    });
                                                                }}
                                                            >
                                                                <TrashIcon className="size-6 text-red-600" />
                                                            </button>
                                                            <div className="flex w-full items-center justify-between text-pretty break-words max-w-full px-2">
                                                                <h2 className="font-semibold text-md">
                                                                    {/* {p?.name?.toUpperCase()} */}
                                                                    {visit?.navigation_filename
                                                                        ? visit.navigation_filename
                                                                        : "N/A"}
                                                                </h2>
                                                                <a
                                                                    className="btn-circle btn-ghost flex justify-center"
                                                                    download={
                                                                        visit.navigation_filename
                                                                    }
                                                                    href={`data:application/octet-stream;base64,${visit.navigation_actual_file}`}
                                                                >
                                                                    <ArrowDownTrayIcon className="size-6 self-center" />
                                                                </a>
                                                            </div>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <div className="text-center text-neutral text-xl font-bold w-full rounded-md bg-neutral-content p-6">
                                                        There is no navigation
                                                        file
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex items-center">
                                    <div className="w-full flex flex-col space-y-2">
                                        <label
                                            className={`form-control w-full`}
                                            title={
                                                errorBadge
                                                    ? errorBadge.detail
                                                    : ""
                                            }
                                        >
                                            <strong className="text-lg">
                                                Comments:{" "}
                                            </strong>

                                            <textarea
                                                className={`textarea textarea-bordered w-full 
                                                                                    `}
                                                disabled={edit ? false : true}
                                                autoComplete="off"
                                                value={
                                                    formState["comments"] ?? ""
                                                }
                                                name={"comments"}
                                                onChange={(e) =>
                                                    dispatch({
                                                        type: "change_value",
                                                        payload: {
                                                            inputName:
                                                                "comments",
                                                            inputValue:
                                                                e.target.value,
                                                        },
                                                    })
                                                }
                                            />
                                            {errorBadge && (
                                                <span className="badge badge-error self-end">
                                                    {errorBadge.code}
                                                </span>
                                            )}
                                        </label>

                                        <Alert msg={commentsMsg} />

                                        {edit && (
                                            <button
                                                className="w-36 self-center btn btn-success rounded"
                                                onClick={() => patchVisit()}
                                            >
                                                {commentLoading && (
                                                    <div
                                                        className="inline-block size-6
                                mx-2 animate-spin rounded-full border-4 border-solid border-current border-e-transparent align-[-0.125em] text-white motion-reduce:animate-[spin_1.5s_linear_infinite]"
                                                        role="status"
                                                    ></div>
                                                )}
                                                Save comments
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="flex flex-col items-center justify-center">
                        <h3 className="font-bold inline-flex items-center text-xl my-2">
                            Visit Images
                            <button
                                className="btn btn-ghost btn-circle ml-2"
                                onClick={() => {
                                    setFileType("visitImage");
                                    setModals({
                                        show: true,
                                        title: "AddFile",
                                        type: "add",
                                    });
                                }}
                            >
                                <PlusCircleIcon
                                    strokeWidth={1.5}
                                    stroke="currentColor"
                                    className="w-8 h-10"
                                />
                            </button>
                        </h3>

                        {images && images.length === 0 ? (
                            <img
                                className="size-60 object-contain rounded"
                                src={defPhoto}
                                alt={"defphoto"}
                            />
                        ) : images && images.length === 1 ? (
                            <div className="w-full break-words text-ellipsis">
                                <div className="absolute z-10">
                                    <button
                                        className="btn "
                                        onClick={() => {
                                            setFileType("image");
                                            setModals({
                                                show: true,
                                                title: "ConfirmDelete",
                                                type: "edit",
                                            });
                                            setDelPhoto(images[0]);
                                        }}
                                        style={{
                                            display: !edit ? "none" : "",
                                        }}
                                    >
                                        <TrashIcon className="size-6 text-red-600" />
                                    </button>
                                </div>
                                <img
                                    className={`${blurPhoto && blurPhoto.id === images[0].id ? "blur-sm " : ""} cursor-zoom-in size-70 object-contain rounded`}
                                    src={`data:image/*;base64,${images[0].actual_image ?? ""}`}
                                    alt={"photos"}
                                    onMouseEnter={() =>
                                        setBlurPhoto({
                                            blur: true,
                                            id: images[0].id,
                                        })
                                    }
                                    onMouseLeave={() => setBlurPhoto(undefined)}
                                    onClick={() => {
                                        setPhoto({
                                            id: images[0].id,
                                            actual_image:
                                                images[0].actual_image ?? "",
                                            description: images[0].description,
                                            name: images[0].name,
                                        });

                                        setModals({
                                            show: true,
                                            title: "ViewStationPhoto",
                                            type: "edit",
                                        });
                                    }}
                                />
                                {images[0].description ? (
                                    <div className="border-t-2 mt-2">
                                        <h3 className="mt-2">Description</h3>
                                        <span className="font-medium">
                                            {images[0].description}
                                        </span>
                                    </div>
                                ) : null}
                            </div>
                        ) : (
                            <div className="slider-container w-[400px]">
                                <Slider {...settings}>
                                    {images &&
                                        images.map((img) => {
                                            return (
                                                <div key={img.id} className="">
                                                    <div className="absolute z-10">
                                                        <button
                                                            style={{
                                                                display: !edit
                                                                    ? "none"
                                                                    : "",
                                                            }}
                                                            className="btn "
                                                            onClick={() => {
                                                                setFileType(
                                                                    "image",
                                                                );
                                                                setModals({
                                                                    show: true,
                                                                    title: "ConfirmDelete",
                                                                    type: "edit",
                                                                });
                                                                setDelPhoto(
                                                                    img,
                                                                );
                                                            }}
                                                        >
                                                            <TrashIcon className="size-6 text-red-600" />
                                                        </button>
                                                    </div>
                                                    <img
                                                        className={`${blurPhoto && blurPhoto.id === img.id ? "blur-sm " : ""} cursor-zoom-in size-70 object-contain rounded`}
                                                        src={`data:image/*;base64,${img.actual_image ?? ""}`}
                                                        alt={"photos"}
                                                        onMouseEnter={() =>
                                                            setBlurPhoto({
                                                                blur: true,
                                                                id: img.id,
                                                            })
                                                        }
                                                        onMouseLeave={() =>
                                                            setBlurPhoto(
                                                                undefined,
                                                            )
                                                        }
                                                        onClick={() => {
                                                            setPhoto({
                                                                id: img.id,
                                                                actual_image:
                                                                    img.actual_image ??
                                                                    "",
                                                                description:
                                                                    img.description,
                                                                name: img.name,
                                                            });

                                                            setModals({
                                                                show: true,
                                                                title: "ViewStationPhoto",
                                                                type: "edit",
                                                            });
                                                        }}
                                                    />
                                                    {img.description && (
                                                        <div className="border-t-2 mt-2 break-words">
                                                            <h3 className="mt-2">
                                                                Description
                                                            </h3>
                                                            <span className="font-medium">
                                                                {
                                                                    img.description
                                                                }
                                                            </span>
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}
                                </Slider>
                            </div>
                        )}
                    </div>
                </div>
                <div className="grid grid-cols-1 space-y-4 grid-flow-dense">
                    <div className="card bg-base-200 grow shadow-xl mr-4">
                        <h2 className="card-title border-b-2 border-base-300 p-2 justify-between">
                            GNSS Files
                            <button
                                className="btn btn-ghost btn-circle ml-2"
                                onClick={() => {
                                    setModals({
                                        show: true,
                                        title: "AddFile",
                                        type: "add",
                                    });
                                    setFileType("gnss");
                                }}
                            >
                                <PlusCircleIcon
                                    strokeWidth={1.5}
                                    stroke="currentColor"
                                    className="w-8 h-10"
                                />
                            </button>
                        </h2>

                        <div className="card-body">
                            <div
                                className={`grid 
                                    ${gnssFiles && gnssFiles.length > 1 ? "grid-cols-2 md:grid-cols-1" : "grid-cols-1"} 
                                    grid-flow-dense gap-2`}
                            >
                                {gnssFiles && gnssFiles.length > 0 ? (
                                    gnssFiles.map((f) => {
                                        return (
                                            <div
                                                className="flex items-center w-full rounded-md bg-neutral-content"
                                                key={f.description + f.id}
                                            >
                                                <div className="flex-grow overflow-hidden ">
                                                    <div className="p-6 flex w-full justify-between items-center">
                                                        <button
                                                            className="btn btn-ghost btn-circle mr-4"
                                                            style={{
                                                                display: !edit
                                                                    ? "none"
                                                                    : "",
                                                            }}
                                                            onClick={() => {
                                                                setFileType(
                                                                    "gnss",
                                                                );

                                                                setModals({
                                                                    show: true,
                                                                    title: "ConfirmDelete",
                                                                    type: "edit",
                                                                });
                                                                setFileToDel(
                                                                    f.id,
                                                                );
                                                            }}
                                                        >
                                                            <TrashIcon className="size-8 text-red-600" />
                                                        </button>
                                                        <div className="flex flex-col w-8/12 text-pretty break-words max-w-full">
                                                            <h2 className="card-title">
                                                                {f.filename}
                                                            </h2>
                                                            <p>
                                                                {f.description}
                                                            </p>
                                                        </div>
                                                        <a
                                                            className="btn-circle btn-ghost flex justify-center w-4/12"
                                                            download={
                                                                f.filename
                                                            }
                                                            href={`data:application/octet-stream;base64,${f.actual_file}`}
                                                        >
                                                            <ArrowDownTrayIcon className="size-6 self-center" />
                                                        </a>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })
                                ) : (
                                    <div className="text-center text-neutral text-2xl font-bold w-full rounded-md bg-neutral-content p-6">
                                        There is no files registered
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                    <div className="card bg-base-200 grow shadow-xl mr-4">
                        <h2 className="card-title border-b-2 border-base-300 p-2 justify-between">
                            Other Files
                            <button
                                className="btn btn-ghost btn-circle ml-2"
                                onClick={() => {
                                    setModals({
                                        show: true,
                                        title: "AddFile",
                                        type: "add",
                                    });
                                    setFileType("other");
                                }}
                            >
                                <PlusCircleIcon
                                    strokeWidth={1.5}
                                    stroke="currentColor"
                                    className="w-8 h-10"
                                />
                            </button>
                        </h2>

                        <div className="card-body">
                            <div
                                className={`grid ${files && files.length > 1 ? "grid-cols-2 md:grid-cols-1" : "grid-cols-1"} grid-flow-dense gap-2`}
                            >
                                {files && files.length > 0 ? (
                                    files.map((f) => {
                                        return (
                                            <div
                                                className="flex items-center w-full rounded-md bg-neutral-content"
                                                key={f.description + f.id}
                                            >
                                                <div className="flex-grow overflow-hidden ">
                                                    <div className="p-6 flex w-full justify-between items-center">
                                                        <button
                                                            className="btn btn-ghost btn-circle mr-4"
                                                            style={{
                                                                display: !edit
                                                                    ? "none"
                                                                    : "",
                                                            }}
                                                            onClick={() => {
                                                                setFileType(
                                                                    "other",
                                                                );

                                                                setModals({
                                                                    show: true,
                                                                    title: "ConfirmDelete",
                                                                    type: "edit",
                                                                });
                                                                setFileToDel(
                                                                    f.id,
                                                                );
                                                            }}
                                                        >
                                                            <TrashIcon className="size-8 text-red-600" />
                                                        </button>
                                                        <div className="flex flex-col w-8/12 text-pretty break-words max-w-full">
                                                            <h2 className="card-title">
                                                                {f.filename}
                                                            </h2>
                                                            <p>
                                                                {f.description}
                                                            </p>
                                                        </div>
                                                        <a
                                                            className="btn-circle btn-ghost flex justify-center w-4/12"
                                                            download={
                                                                f.filename
                                                            }
                                                            href={`data:application/octet-stream;base64,${f.actual_file}`}
                                                        >
                                                            <ArrowDownTrayIcon className="size-6 self-center" />
                                                        </a>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })
                                ) : (
                                    <div className="text-center text-neutral text-2xl font-bold w-full rounded-md bg-neutral-content p-6">
                                        There is no files registered
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            {modals && modals?.title === "AddFile" && (
                <AddFileModal
                    id={visitId}
                    visit={visit}
                    pageType={"visit"}
                    fileType={fileType ?? ""}
                    setStateModal={setModals}
                    reFetch={() => {
                        setFileType(undefined);
                        getAll();
                    }}
                />
            )}

            {modals && modals?.title === "AddVisitPeople" && (
                <VisitPeopleModal
                    people={people}
                    visit={visit}
                    setStateModal={setModals}
                    reFetch={() => getAll()} // En este caso closeModal es el fetch de visits que hace la pagina.
                />
            )}

            {modals && modals?.title === "AddVisitCampaign" && (
                <VisitCampaignModal
                    campaigns={campaigns}
                    visit={visit}
                    setStateModal={setModals}
                    reFetch={() => {
                        getAll();
                    }}
                    // En este caso closeModal es el fetch de visits que hace la pagina.
                />
            )}

            {modals && modals?.title === "ViewStationPhoto" && (
                <ImageModal
                    photo={photo ?? undefined}
                    closeModal={() => {
                        setPhoto(undefined);
                    }}
                    setStateModal={setModals}
                />
            )}

            {modals && modals?.title === "ConfirmDelete" && (
                <ConfirmDeleteModal
                    loading={loading}
                    msg={fileMsg || peopleMsg}
                    confirmRemove={() =>
                        fileType
                            ? fileType === "gnss"
                                ? delVisitGnssFile()
                                : fileType === "other"
                                  ? delVisitAttachedFile()
                                  : fileType === "image"
                                    ? delVisitImage()
                                    : delVisitFiles()
                            : personToDel
                              ? delPeople()
                              : delCampaign()
                    }
                    closeModal={() => {
                        setModals({
                            show: false,
                            title: "",
                            type: "edit",
                        });
                        setFileType(undefined);
                        setFileToDel(undefined);
                        setDelPhoto(undefined);
                        setFileMsg(undefined);
                        setPeopleMsg(undefined);
                        setPersonToDel(undefined);
                        getAll();
                    }}
                />
            )}
        </Modal>
    );
};

export default StationVisitDetailModal;
