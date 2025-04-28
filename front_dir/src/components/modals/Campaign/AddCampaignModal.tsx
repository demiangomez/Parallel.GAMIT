import { useEffect, useState } from "react";
import { Alert, ConfirmDeleteModal, Menu, MenuButton, MenuContent, Modal } from "@componentsReact";
import { useApi, useAuth, useFormReducer } from "@hooks";
import {
    delStationCampaignService,
    patchStationCampaignService,
    postStationCampaignService,
} from "@services";

import { CampaignsData, ErrorResponse, Errors, People } from "@types";

import { apiOkStatuses, showModal } from "@utils";
import { CAMPAIGN_STATE } from "@utils/reducerFormStates";

interface Props {
    modalType: string;
    campaign: CampaignsData | undefined;
    reFetch: () => void;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
    people: People[] | undefined;
}

const AddCampaignModal = ({
    campaign,
    modalType,
    reFetch,
    setStateModal,
    people,
}: Props) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [loading, setLoading] = useState<boolean>(false);

    const [selectedPeople, setSelectedPeople] = useState<string[] | undefined>([]);

    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [showMenu, setShowMenu] = useState<{show: boolean, type: string} | undefined>({show: false, type:""});

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const { formState, dispatch } = useFormReducer(CAMPAIGN_STATE);

    const addCampaign = async () => {
        try {
            setLoading(true);
            const res = await postStationCampaignService<any>(api, formState);
            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setMsg({
                    status: res.statusCode,
                    msg: "Campaign added successfully",
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
            setLoading(true);
            const res = await delStationCampaignService<ErrorResponse>(
                api,
                Number(campaign?.id),
            );
            if (res) {
                if ("status" in res && res.status === "success") {
                    setMsg({
                        status: res.statusCode,
                        msg: res.msg,
                    });
                } else {
                    setMsg({
                        status: res.statusCode,
                        msg: res.response.type,
                        errors: res.response,
                    });
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const editCampaign = async () => {
        try {
            setLoading(true);
            
            const res = await patchStationCampaignService<
                CampaignsData | ErrorResponse
            >(api, Number(campaign?.id), formState);
            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setMsg({
                    status: res.statusCode,
                    msg: "Campaign edited successfully",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleCloseModal = () => {
        reFetch();
    };

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const numberPeople = formState.default_people.map((p: string) => people?.find((person) => `${person.first_name} ${person.last_name}` === p)?.id?.toString());
        formState.default_people = numberPeople as string[];
        if (modalType === "edit") {
            await editCampaign();
        } else if (modalType === "add") {
            await addCampaign();
        }
    };

    const errorBadge = msg?.errors?.errors?.map((e) => e.attr);

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    useEffect(() => {
        if (campaign) {
            dispatch({
                type: "set",
                payload: campaign,
            });
            if(campaign.default_people){
                const peopleNames = campaign.default_people.map((p: number) => {
                    const person = people?.find((person) => person.id === p);
                    return person ? `${person.first_name} ${person.last_name}` : "";
                });
                dispatch({
                    type: "change_value",
                    payload: {
                        inputName: "default_people",
                        inputValue: peopleNames,
                    },
                });
                setSelectedPeople(peopleNames);
            }
        }
    }, [campaign]);

    useEffect(() => {
        dispatch({
            type: "change_value",
            payload: {
                inputName: "default_people",
                inputValue: selectedPeople,
            },
        });
    }, [selectedPeople]);

    return (
        <Modal
            close={false}
            modalId={"EditCampaigns"}
            size={"sm"}
            handleCloseModal={() => handleCloseModal()}
            setModalState={setStateModal}
        >
            <div className="w-full flex grow mb-2">
                <h3 className="font-bold text-center text-2xl my-2 w-full self-center">
                    {modalType?.charAt(0).toUpperCase() + modalType?.slice(1)}
                </h3>
            </div>
            <form className="space-y-4" onSubmit={handleSubmit}>
                <div className="grid grid-cols-1 gap-4">
                    {Object.keys(formState || {}).map((key, index) => {
                        const disabled = key === "id";
                        const inputsToDatePicker = ["start_date", "end_date"];
                        if (key === "default_people") {
                            return(
                            <div className="">
                                <div className="flex flex-col space-y-1">
                                    <label
                                        key={index}
                                        className={"w-full input input-bordered flex items-center text-nowrap m"}
                                        title={
                                            errorBadge?.includes(key)
                                                ? msg?.errors?.errors.find(
                                                    (e) => e.attr === key,
                                                )?.detail
                                                : Array.isArray(formState[key as keyof typeof formState])
                                                    ? (formState[key as keyof typeof formState] as string[]).join(', ')
                                                    : (formState[key as keyof typeof formState] ?? "").toString()
                                        }
                                    >
                                        <div className="label">
                                            <span className="font-bold">
                                                {key
                                                    .toUpperCase()
                                                    .replace("_", " ")
                                                    .replace("_", " ")}
                                            </span>
                                        </div>
                                        <input 
                                            type="text" 
                                            className="grow"
                                            value={formState.default_people?.join(", ") ?? ""}
                                            onChange={(e) => {
                                                dispatch({
                                                    type: "change_value",
                                                    payload: {
                                                        inputName: key,
                                                        inputValue: e.target.value,
                                                    },
                                                });
                                            }}
                                        />
                                        <MenuButton
                                            setShowMenu={setShowMenu}
                                            showMenu={showMenu}
                                            typeKey={"name"}
                                        />
                                    </label>
                                </div>
                                {showMenu?.show && showMenu?.type === "name" && 
                                    <Menu>
                                        {people && people.length > 0 && people.map((p) => (
                                            <MenuContent
                                                key={p.id +
                                                    p.first_name}
                                                typeKey={key}
                                                value={`${p.first_name} ${p.last_name}`}
                                                setShowMenu={setShowMenu}
                                                dispatch={dispatch}
                                                multipleSelected={selectedPeople}
                                                multiple={true}
                                                setMultipleSelected={setSelectedPeople}
                                            />
                                        ))}
                                    </Menu>
                                } 
                            </div>
                            )
                        }
                        else{
                            return (
                                <div key={key + index} className="flex w-full">
                                    <label
                                        key={index}
                                        className={`w-full input input-bordered flex items-center gap-2 ${
                                            errorBadge?.includes(key)
                                                ? "input-error"
                                                : ""
                                        } `}
                                        title={
                                            errorBadge?.includes(key)
                                                ? msg?.errors?.errors.find(
                                                    (e) => e.attr === key,
                                                )?.detail
                                                : Array.isArray(formState[key as keyof typeof formState])
                                                    ? (formState[key as keyof typeof formState] as string[]).join(', ')
                                                    : (formState[key as keyof typeof formState] ?? "").toString()
                                        }
                                    >
                                        <div className="label text-nowrap">
                                            <span className="font-bold">
                                                {key
                                                    .toUpperCase()
                                                    .replace("_", " ")
                                                    .replace("_", " ")}
                                            </span>
                                        </div>
                                        <input
                                            type={
                                                inputsToDatePicker.includes(key)
                                                    ? "date"
                                                    : "text"
                                            }
                                            value={
                                                formState[
                                                    key as keyof typeof formState
                                                ] ?? ""
                                            }
                                            onChange={(e) => {
                                                const value = e.target.value;
                                                dispatch({
                                                    type: "change_value",
                                                    payload: {
                                                        inputName: key,
                                                        inputValue: value,
                                                    },
                                                });
                                            }}
                                            className="w-full"
                                            autoComplete="off"
                                            placeholder={
                                                inputsToDatePicker.includes(key)
                                                    ? "YYYY-MM-DD"
                                                    : ""
                                            }
                                            disabled={disabled}
                                        />
                                        {errorBadge && errorBadge.includes(key) && (
                                            <span className="badge badge-error absolute right-0 mb-12 mr-2">
                                                {errorBadge.includes(key)
                                                    ? msg?.errors?.errors.find(
                                                        (e) => e.attr === key,
                                                    )?.code
                                                    : ""}
                                            </span>
                                        )}
                                    </label>
                                </div>
                            );
                        }
                    })}
                    
                </div>
                <Alert msg={msg} />
                {loading && (
                    <div className="w-full text-center">
                        <span className="loading loading-spinner loading-lg self-center"></span>
                    </div>
                )}
                <div className="flex w-full justify-center space-x-4">
                    {modalType === "edit" && (
                        <button
                            type="button"
                            className="btn btn-error w-3/12"
                            disabled={apiOkStatuses.includes(
                                Number(msg?.status),
                            )}
                            onClick={() =>
                                setModals({
                                    show: true,
                                    title: "ConfirmDelete",
                                    type: "edit",
                                })
                            }
                        >
                            Remove
                        </button>
                    )}
                    <button
                        className="btn btn-success self-center w-3/12"
                        disabled={
                            loading ||
                            apiOkStatuses.includes(Number(msg?.status))
                        }
                    >
                        {" "}
                        Save{" "}
                    </button>
                    {modals && modals?.title === "ConfirmDelete" && (
                        <ConfirmDeleteModal
                            msg={msg}
                            loading={loading}
                            confirmRemove={() => delCampaign()}
                            closeModal={() => {
                                setModals({
                                    show: false,
                                    title: "",
                                    type: "edit",
                                });
                            }}
                        />
                    )}
                </div>
            </form>
        </Modal>
    );
};

export default AddCampaignModal;
