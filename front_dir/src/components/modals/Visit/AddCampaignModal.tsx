/* eslint-disable @typescript-eslint/no-unused-vars */
import { useEffect, useState } from "react";
import { Alert, Menu, MenuButton, MenuContent, Modal } from "@componentsReact";

import { useApi, useAuth, useFormReducer } from "@hooks";

import { ErrorResponse, Errors, StationCampaignsData } from "@types";
import { apiOkStatuses } from "@utils";
import { patchStationVisitService } from "@services";

interface Props {
    campaigns: StationCampaignsData[] | undefined;
    visit: any;
    reFetch: () => void;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
}

const AddCampaignModal = ({
    campaigns,
    visit,
    reFetch,
    setStateModal,
}: Props) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const visitId = visit.id;

    const [loading, setLoading] = useState<boolean>(false);

    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [matchingCampaigns, setMatchingCampaigns] = useState<
        StationCampaignsData[] | undefined
    >(undefined);

    const [showMenu, setShowMenu] = useState<
        { type: string; show: boolean } | undefined
    >(undefined);

    const { formState, dispatch } = useFormReducer(visit);

    const addCampaign = async () => {
        try {
            if (!visitId) return null;
            setLoading(true);

            const {
                name,
                people_id,
                comments,
                navigation_actual_file,
                log_sheet_actual_file,
                log_sheet_filename,
                navigation_filename,
                ...rest
            } = formState;

            rest.campaign = name.split("(").pop()?.split(")")[0] ?? null;

            const formData = new FormData();

            const campaignToAdd = campaigns?.find(
                (c) => c.name === rest.campaign,
            );

            rest.campaign = campaignToAdd?.id ?? null;

            Object.entries(rest).forEach(([key, value]) => {
                if (key === "campaign") {
                    formData.append(key, String(value));
                } else if (key === "people" && Array.isArray(value)) {
                    value.forEach((p: { id: number; name: string }) => {
                        formData.append("people", String(p.id));
                    });
                } else {
                    formData.append(key, value as unknown as string);
                }
            });

            const res = await patchStationVisitService<ErrorResponse>(
                api,
                visitId,
                formData,
            );
            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setMsg({
                    status: 200,
                    msg: "Campaigns Visit updated successfully",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (formState.campaign_id) {
            const campaignToAdd = campaigns?.find(
                (c) => c.id === Number(formState.campaign_id),
            );

            dispatch({
                type: "change_value",
                payload: {
                    inputName: "name",
                    inputValue: campaignToAdd?.name ?? "",
                },
            });
        }
    }, [formState.campaign_id]);

    const handleCloseModal = () => {
        reFetch();
    };

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        addCampaign();
    };

    const errorBadge = msg?.errors?.errors?.map((e) => e.attr);

    return (
        <Modal
            close={false}
            modalId={"AddVisitCampaign"}
            size={"sm"}
            handleCloseModal={() => handleCloseModal()}
            setModalState={setStateModal}
        >
            <div className="w-full flex grow mb-2">
                <h3 className="font-bold text-center text-2xl my-2 w-full self-center">
                    Add
                </h3>
            </div>
            <form className="form-control space-y-4" onSubmit={handleSubmit}>
                <div className="form-control space-y-2">
                    <>
                        <label
                            className={`w-full input input-bordered flex items-center gap-2 ${errorBadge?.includes("campaign") ? "input-error" : ""}`}
                            title={
                                errorBadge?.includes("campaign")
                                    ? msg?.errors?.errors.find(
                                          (e) => e.attr === "campaign",
                                      )?.detail
                                    : "Campaign"
                            }
                        >
                            <div className="label text-2xl">
                                <span className="font-bold">Campaigns</span>
                            </div>
                            <input
                                type="text"
                                value={formState["name"] ?? ""}
                                onChange={(e) => {
                                    const value = e.target.value;
                                    dispatch({
                                        type: "change_value",
                                        payload: {
                                            inputName: "name",
                                            inputValue: value,
                                        },
                                    });
                                    const match = campaigns?.filter(
                                        (c) =>
                                            c.name
                                                .toLowerCase()
                                                .includes(
                                                    value.toLowerCase(),
                                                ) ||
                                            c.start_date.includes(value) ||
                                            c.end_date.includes(value),
                                    );

                                    setMatchingCampaigns(match);
                                }}
                                className="grow"
                                autoComplete="off"
                            />
                            {errorBadge && errorBadge.includes("campaign") && (
                                <span className="badge badge-error absolute right-0 mb-12 mr-2">
                                    {errorBadge.includes("campaign")
                                        ? msg?.errors?.errors.find(
                                              (e) => e.attr === "campaign",
                                          )?.code
                                        : ""}
                                </span>
                            )}

                            <MenuButton
                                setShowMenu={setShowMenu}
                                showMenu={showMenu}
                                typeKey={"name"}
                            />
                        </label>
                        {showMenu?.show && showMenu.type === "name" ? (
                            <Menu>
                                {(matchingCampaigns &&
                                matchingCampaigns.length > 0
                                    ? matchingCampaigns
                                    : campaigns
                                )?.map((c) => (
                                    <MenuContent
                                        key={c.id}
                                        disabled={c.id === formState.campaign}
                                        typeKey={"name"}
                                        value={
                                            "(" +
                                            c.name +
                                            ")" +
                                            " " +
                                            c.start_date +
                                            " - " +
                                            c.end_date
                                        }
                                        // alterValue={String(c.id)}
                                        dispatch={dispatch}
                                        setShowMenu={setShowMenu}
                                    />
                                ))}
                            </Menu>
                        ) : null}
                    </>
                </div>
                <Alert msg={msg} />
                {loading && (
                    <div className="w-full text-center">
                        <span className="loading loading-spinner loading-lg self-center"></span>
                    </div>
                )}
                <button
                    className="btn btn-success self-center w-3/12"
                    disabled={
                        loading || apiOkStatuses.includes(Number(msg?.status))
                    }
                >
                    {" "}
                    Save{" "}
                </button>
            </form>
        </Modal>
    );
};

export default AddCampaignModal;
