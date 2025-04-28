import { useEffect, useMemo, useState } from "react";
import { Alert, MenuButton, MenuCheckbox, Modal } from "@componentsReact";

import { Rnd } from "react-rnd";

import { BookmarkIcon, XMarkIcon } from "@heroicons/react/24/outline";

import {
    getEndpointClustersService,
    postRoleService,
    putRoleService,
} from "@services";

import { useApi, useAuth, useFormReducer } from "@hooks";

import {
    ClusterServiceData,
    EndpointCluster,
    ErrorResponse,
    Errors,
    Role,
} from "@types";

import { apiOkStatuses, showModal } from "@utils";

interface AddRoleModalProps {
    Role: Role | undefined;
    modalType: string;
    reFetch: () => void;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
    setRole: React.Dispatch<React.SetStateAction<Role | undefined>>;
}

type CloseFunction = () => void;

const Actions = ({ close }: { close: CloseFunction }) => {
    return (
        <div className="grid grid-cols-1 grid-flow-dense gap-3 relative ">
            <button
                type="button"
                onClick={() => close()}
                className="justify-self-end"
            >
                <XMarkIcon className="size-5" />
            </button>
            <div className="grid grid-cols-1 card p-4 border-[1px] space-y-2 border-neutral-300 w-full">
                <span className="w-full flex justify-center font-bold text-xl">
                    Permission Levels
                </span>
                <span>
                    <strong>Read:</strong> User can only view the resource.
                </span>
                <span>
                    <strong>Read-Create (if available):</strong> User can view
                    the resource and create new ones, but cannot modify any
                    existing resources.
                </span>
                <span>
                    <strong>Read-Write (if available):</strong> User can view,
                    create, and modify resources.
                </span>
            </div>
        </div>
    );
};

const AddRoleModal = ({
    Role,
    modalType,
    reFetch,
    setStateModal,
    setRole,
}: AddRoleModalProps) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [loading, setLoading] = useState<boolean>(false);
    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const [showMenu, setShowMenu] = useState<
        { type: string; show: boolean } | undefined
    >(undefined);

    const [actionsManual, setActionsManual] = useState<boolean>(false);

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const [endpoints, setEndpoints] = useState<string[]>([]);
    const [allChecked, setAllchecked] = useState<
        { [key: string]: boolean } | undefined
    >(undefined);

    const roleMockup = {
        roleName: "",
        permissions: [
            { name: "api", id: "1" },
            { name: "front", id: "2" },
        ],
        permissionSelected: "",
        allowAllEndpoints: false,
        groups: {
            api: {},
            front: {},
        },
        selectedGroup: {},
        activeRole: true,
    };

    const getEndpointClusters = async () => {
        try {
            const res = await getEndpointClustersService<ClusterServiceData>(
                api,
                {
                    offset: 0,
                    limit: 0,
                    role_type:
                        formState.permissionSelected === "api"
                            ? "API"
                            : "FRONT",
                },
            );

            dispatch({
                type: "change_value",
                payload: {
                    inputName: `groups.${formState.permissionSelected}`,
                    inputValue: res.data as any,
                },
            });

            dispatch({
                type: "change_value",
                payload: {
                    inputName: "selectedGroup",
                    inputValue: res.data as any,
                },
            });
        } catch (err) {
            console.error(err);
        }
    };

    const postRole = async () => {
        try {
            setLoading(true);
            const data = {
                name: formState.roleName,
                role_api: formState.permissionSelected === "api",
                role_front: formState.permissionSelected === "front",
                allow_all: formState.allowAllEndpoints,
                is_active: formState.activeRole,
                endpoints_clusters: endpointClusters,
            };
            const res = await postRoleService<Role | ErrorResponse>(api, data);
            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setMsg({
                    status: res.statusCode,
                    msg: "Role added successfully",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const putRole = async () => {
        try {
            setLoading(true);
            const data = {
                name: formState.roleName,
                role_api: formState.permissionSelected === "api",
                role_front: formState.permissionSelected === "front",
                allow_all: formState.allowAllEndpoints,
                is_active: formState.activeRole,
                endpoints_clusters: endpointClusters,
            };

            const res = await putRoleService<Role | ErrorResponse>(
                api,
                Number(Role?.id),
                data,
            );
            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setMsg({
                    status: res.statusCode,
                    msg: "Role edited successfully",
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const fetch = () => {
        reFetch();
    };

    useEffect(() => {
        fetch();
    }, []); //eslint-disable-line

    const { dispatch, formState } = useFormReducer(roleMockup);

    useEffect(() => {
        if (modalType === "edit" && Role) {
            dispatch({
                type: "change_value",
                payload: {
                    inputName: "roleName",
                    inputValue: Role?.name,
                },
            });

            dispatch({
                type: "change_value",
                payload: {
                    inputName: "allowAllEndpoints",
                    inputValue: Role?.allow_all,
                },
            });

            dispatch({
                type: "change_value",
                payload: {
                    inputName: "permissionSelected",
                    inputValue: Role?.role_api ? "api" : "front",
                },
            });

            dispatch({
                type: "change_value",
                payload: {
                    inputName: "activeRole",
                    inputValue: Role?.is_active,
                },
            });

            setEndpoints(() => {
                if (Role.endpoints_clusters.length > 0) {
                    return Role.endpoints_clusters.map((e) => {
                        return e.toString();
                    });
                } else {
                    return [];
                }
            });
        }
    }, [Role, modalType]); //eslint-disable-line

    useEffect(() => {
        if (formState.permissionSelected) {
            getEndpointClusters();
        }
    }, [formState.permissionSelected]); //eslint-disable-line

    const handleChange = (e: HTMLInputElement | HTMLSelectElement) => {
        const { name, value } = e;

        dispatch({
            type: "change_value",
            payload: {
                inputName: name,
                inputValue: value,
            },
        });
    };

    const selectedGroup = useMemo(() => {
        return formState.selectedGroup;
    }, [formState]);

    const clustersToShow = useMemo(() => {
        return selectedGroup
            ? Object.entries(selectedGroup as EndpointCluster).map(
                  ([key, value]) => {
                      const cluster: string[] = [];
                      value.map((c) => {
                          cluster.push(
                              c.cluster_type?.name
                                  ? c.cluster_type.name +
                                        "#" +
                                        c.id +
                                        "#" +
                                        c.description
                                  : c.description?.split(" ")[1] +
                                        "#" +
                                        c.id +
                                        "#" +
                                        c.description,
                          );
                      });

                      return {
                          [key]: cluster,
                      };
                  },
              )
            : [];
    }, [selectedGroup]);

    const endpointClusters = useMemo(() => {
        return endpoints.map((e) => {
            const endpoint = Number(e);

            return endpoint;
        });
    }, [endpoints]);

    const handleCloseModal = () => {
        fetch();
        setRole(undefined);
        if (modalType !== "edit") {
            dispatch({
                type: "set",
                payload: roleMockup,
            });
        }
        setMsg(undefined);
    };

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setMsg(undefined);
        if (modalType === "add") {
            postRole();
        } else {
            putRole();
        }
    };

    const nameErrorBadge = msg?.errors?.errors.find(
        (error) => error.attr === "name",
    );

    const endpointsErrorBadge = msg?.errors?.errors.find(
        (error) => error.attr === "endpoints_clusters",
    );

    const pagesErrorBadge = msg?.errors?.errors.find(
        (error) => error.attr === "pages",
    );

    const rndOptions = {
        x: window.innerWidth / 2 - 310,
        y: window.innerHeight / 2 - 360,
        width: 620,
        height: 620,
    };

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    return (
        <>
            {actionsManual && modals?.title === "rnd_caption" && (
                <dialog id="rnd_caption-modal" className="modal">
                    <Rnd
                        default={rndOptions}
                        minWidth={620}
                        minHeight={200}
                        maxHeight={270}
                        bounds={"window"}
                        className="z-[100] card border-[1px] border-neutral-300 shadow-2xl bg-base-100 p-4 overflow-y-hidden scrollbar-base overflow-x-hidden"
                    >
                        <Actions close={() => setActionsManual(false)} />
                    </Rnd>
                </dialog>
            )}
            <Modal
                close={false}
                modalId={"AddRole"}
                size={"smPlus"}
                handleCloseModal={() => handleCloseModal()}
                setModalState={setStateModal}
            >
                <div className="w-full flex grow mb-2">
                    <h3 className="font-bold text-center text-2xl my-2 w-full self-center">
                        {modalType?.charAt(0).toUpperCase() +
                            modalType?.slice(1)}
                    </h3>
                </div>
                <form
                    className="form-control space-y-4"
                    onSubmit={handleSubmit}
                >
                    <div className="flex flex-col space-y-4">
                        <div className="flex w-full">
                            <label
                                className={`w-full input input-bordered flex items-center gap-2 ${nameErrorBadge ? "input-error" : ""} `}
                                title={
                                    nameErrorBadge
                                        ? nameErrorBadge.detail
                                        : "Role Name"
                                }
                            >
                                <div className="label">
                                    <span className="font-bold">ROLE NAME</span>
                                </div>
                                <input
                                    name={"roleName"}
                                    value={formState["roleName"] ?? ""}
                                    onChange={(e) => {
                                        handleChange(e.target);
                                    }}
                                    className="grow "
                                    autoComplete="off"
                                />
                                <div className="label">
                                    <span
                                        className={`font-bold ${formState.activeRole ? "text-green-700" : "text-red-700"} `}
                                    >
                                        {formState.activeRole
                                            ? "ACTIVE"
                                            : "INACTIVE"}
                                    </span>
                                </div>
                            </label>
                            <select
                                value={formState.permissionSelected || ""}
                                className="select select-bordered mx-4 text-center font-bold w-fit"
                                onChange={(e) => {
                                    setShowMenu(undefined);
                                    setEndpoints([]);
                                    setAllchecked(undefined);
                                    dispatch({
                                        type: "change_value",
                                        payload: {
                                            inputName: "permissionSelected",
                                            inputValue: e.target.value,
                                        },
                                    });
                                    dispatch({
                                        type: "change_value",
                                        payload: {
                                            inputName: "selectedGroup",
                                            inputValue:
                                                e.target.value === "api"
                                                    ? (formState.groups[
                                                          e.target.value
                                                      ] as any)
                                                    : e.target.value ===
                                                          "front" &&
                                                      (formState.groups[
                                                          e.target.value
                                                      ] as any),
                                        },
                                    });
                                }}
                            >
                                <option disabled value="">
                                    Select a permission
                                </option>
                                {formState.permissions?.map((role) => (
                                    <option key={role.id} value={role.name}>
                                        {role.name.toUpperCase()}
                                    </option>
                                ))}
                            </select>

                            <input
                                type="checkbox"
                                className={`toggle my-auto`}
                                style={{
                                    borderRadius: "50px",
                                    color: formState.activeRole
                                        ? "rgb(21 128 61)"
                                        : "rgb(185 28 28)",
                                }}
                                onChange={(e) => {
                                    dispatch({
                                        type: "change_value",
                                        payload: {
                                            inputName: "activeRole",
                                            inputValue: e.target.checked,
                                        },
                                    });
                                }}
                                checked={formState.activeRole}
                            />
                        </div>
                        <div className="flex w-full justify-center">
                            <input
                                type="checkbox"
                                className="checkbox mr-2"
                                title={"Check to allow all endpoints"}
                                checked={formState.allowAllEndpoints}
                                onChange={() => {
                                    dispatch({
                                        type: "change_value",
                                        payload: {
                                            inputName: "allowAllEndpoints",
                                            inputValue:
                                                !formState.allowAllEndpoints,
                                        },
                                    });
                                }}
                            />
                            <label className="">
                                Check to allow all endpoints
                            </label>
                        </div>
                        {!formState.allowAllEndpoints &&
                            formState.selectedGroup &&
                            Object.keys(formState.selectedGroup)?.length >
                                0 && (
                                <>
                                    <label
                                        className={`w-full input 
                                    input-bordered flex justify-between 
                                    items-center gap-2 ${endpointsErrorBadge || pagesErrorBadge ? "input-error" : ""}`}
                                        title={`${
                                            endpointsErrorBadge ||
                                            pagesErrorBadge
                                                ? endpointsErrorBadge?.detail ||
                                                  pagesErrorBadge?.detail
                                                : "Endpoints to allow"
                                        }`}
                                    >
                                        <div className="label">
                                            <span className="font-bold">
                                                ENDPOINTS TO ALLOW
                                            </span>
                                        </div>{" "}
                                        <MenuButton
                                            setShowMenu={setShowMenu}
                                            showMenu={showMenu}
                                            typeKey="endpoints"
                                        />
                                    </label>
                                    {showMenu?.show &&
                                        showMenu?.type === "endpoints" && (
                                            <ul // NOTA: PARA RESOLVER EL PROBLEMA DEL WRAP PUEDO HACER 2 MENUES ?¿ DOS UL UNO QUE TENGA
                                                // LOS OBJETOS Y EL OTRO QUE TENGA LOS INDIVIDUALES SI ES ASÍ SACAR EL OVERFLOW-X-AUTO
                                                className="menu overflow-x-auto items-center w-full max-h-[25rem] mt-2 
                                    bg-neutral-content rounded-box overflow-y-auto space-y-6 relative"
                                                style={{
                                                    justifyContent:
                                                        "space-between",
                                                    display: "grid",
                                                    gridTemplateColumns:
                                                        "repeat(3,1fr)",
                                                }}
                                            >
                                                <div className="absolute top-2 left-2">
                                                    <button
                                                        className="hover:scale-110 transition-all duration-200"
                                                        type="button"
                                                        title="Permission Levels"
                                                        onClick={() => {
                                                            setModals({
                                                                show: true,
                                                                title: "rnd_caption",
                                                                type: "none",
                                                            });
                                                            setActionsManual(
                                                                !actionsManual,
                                                            );
                                                        }}
                                                    >
                                                        <BookmarkIcon className="size-6" />
                                                    </button>
                                                </div>
                                                {selectedGroup &&
                                                    Object.keys(selectedGroup)
                                                        ?.length > 0 &&
                                                    clustersToShow.map(
                                                        (e, idx) => {
                                                            if (
                                                                typeof e ===
                                                                "string"
                                                            ) {
                                                                return (
                                                                    <MenuCheckbox
                                                                        liKey={
                                                                            e +
                                                                            String(
                                                                                idx,
                                                                            )
                                                                        }
                                                                        inputTitle={
                                                                            e
                                                                        }
                                                                        inputChecked={endpoints.includes(
                                                                            e,
                                                                        )}
                                                                        inputText={
                                                                            e
                                                                        }
                                                                        inputDisabled={
                                                                            false
                                                                        }
                                                                        isCheckbox={
                                                                            true
                                                                        }
                                                                        handleChange={() => {
                                                                            setEndpoints(
                                                                                (
                                                                                    prev,
                                                                                ) =>
                                                                                    prev.includes(
                                                                                        e,
                                                                                    )
                                                                                        ? prev.filter(
                                                                                              (
                                                                                                  el,
                                                                                              ) =>
                                                                                                  el !==
                                                                                                  e,
                                                                                          )
                                                                                        : [
                                                                                              ...prev,
                                                                                              e,
                                                                                          ],
                                                                            );
                                                                        }}
                                                                    />
                                                                );
                                                            } else {
                                                                const values =
                                                                    e[
                                                                        Object.keys(
                                                                            e,
                                                                        )[0]
                                                                    ];
                                                                const endpointValues =
                                                                    values.map(
                                                                        (e) => {
                                                                            return e.split(
                                                                                "#",
                                                                            )[1];
                                                                        },
                                                                    );

                                                                const title =
                                                                    Object.keys(
                                                                        e,
                                                                    )[0];

                                                                return (
                                                                    <li className="font-semibold text-lg w-fit justify-between">
                                                                        <a className="w-full justify-around hover:cursor-default">
                                                                            <label className="cursor-pointer label">
                                                                                <input
                                                                                    type="checkbox"
                                                                                    className="checkbox mr-2"
                                                                                    title={
                                                                                        title
                                                                                    }
                                                                                    checked={
                                                                                        allChecked?.[
                                                                                            title
                                                                                        ]
                                                                                    }
                                                                                    onChange={(
                                                                                        event,
                                                                                    ) => {
                                                                                        if (
                                                                                            event
                                                                                                .target
                                                                                                .checked
                                                                                        ) {
                                                                                            setEndpoints(
                                                                                                (
                                                                                                    prev,
                                                                                                ) => [
                                                                                                    ...new Set(
                                                                                                        [
                                                                                                            ...prev,
                                                                                                            ...endpointValues,
                                                                                                        ],
                                                                                                    ),
                                                                                                ],
                                                                                            );
                                                                                            setAllchecked(
                                                                                                (
                                                                                                    prev,
                                                                                                ) => ({
                                                                                                    ...prev,
                                                                                                    [title]:
                                                                                                        true,
                                                                                                }),
                                                                                            );
                                                                                        } else {
                                                                                            setEndpoints(
                                                                                                (
                                                                                                    prev,
                                                                                                ) =>
                                                                                                    prev.filter(
                                                                                                        (
                                                                                                            endpoint,
                                                                                                        ) =>
                                                                                                            !endpointValues.includes(
                                                                                                                endpoint,
                                                                                                            ),
                                                                                                    ),
                                                                                            );
                                                                                            setAllchecked(
                                                                                                (
                                                                                                    prev,
                                                                                                ) => {
                                                                                                    const newAllChecked =
                                                                                                        {
                                                                                                            ...prev,
                                                                                                        };
                                                                                                    delete newAllChecked[
                                                                                                        title
                                                                                                    ];
                                                                                                    return newAllChecked;
                                                                                                },
                                                                                            );
                                                                                        }
                                                                                    }}
                                                                                />
                                                                                <span className="label-text ml-2">
                                                                                    All
                                                                                </span>
                                                                            </label>
                                                                            {title.toUpperCase()}
                                                                        </a>
                                                                        <ul>
                                                                            {values.map(
                                                                                (
                                                                                    endpoint,
                                                                                    idx,
                                                                                ) => (
                                                                                    <li
                                                                                        key={
                                                                                            endpoint +
                                                                                            idx
                                                                                        }
                                                                                    >
                                                                                        <a className="w-full text-center hover:cursor-default">
                                                                                            <input
                                                                                                type="checkbox"
                                                                                                className="checkbox mr-2"
                                                                                                title={
                                                                                                    endpoint.split(
                                                                                                        "#",
                                                                                                    )[0]
                                                                                                }
                                                                                                checked={endpoints.includes(
                                                                                                    endpoint.split(
                                                                                                        "#",
                                                                                                    )[1],
                                                                                                )}
                                                                                                disabled={
                                                                                                    allChecked?.[
                                                                                                        title
                                                                                                    ]
                                                                                                }
                                                                                                onChange={() =>
                                                                                                    setEndpoints(
                                                                                                        (
                                                                                                            prev,
                                                                                                        ) =>
                                                                                                            prev.includes(
                                                                                                                endpoint.split(
                                                                                                                    "#",
                                                                                                                )[1],
                                                                                                            )
                                                                                                                ? prev.filter(
                                                                                                                      (
                                                                                                                          el,
                                                                                                                      ) =>
                                                                                                                          el !==
                                                                                                                          endpoint.split(
                                                                                                                              "#",
                                                                                                                          )[1],
                                                                                                                  )
                                                                                                                : [
                                                                                                                      ...prev,

                                                                                                                      endpoint.split(
                                                                                                                          "#",
                                                                                                                      )[1],
                                                                                                                  ],
                                                                                                    )
                                                                                                }
                                                                                            />
                                                                                            <div className="flex flex-col">
                                                                                                <span>
                                                                                                    {
                                                                                                        endpoint.split(
                                                                                                            "#",
                                                                                                        )[0]
                                                                                                    }
                                                                                                </span>
                                                                                                <span className="text-sm font-light">
                                                                                                    {
                                                                                                        endpoint.split(
                                                                                                            "#",
                                                                                                        )[2]
                                                                                                    }
                                                                                                </span>
                                                                                            </div>
                                                                                        </a>
                                                                                    </li>
                                                                                ),
                                                                            )}
                                                                        </ul>
                                                                    </li>
                                                                );
                                                            }
                                                        },
                                                    )}
                                            </ul>
                                        )}
                                </>
                            )}
                        <Alert msg={msg} />

                        <button
                            className="btn btn-success w-6/12 self-center"
                            type="submit"
                            disabled={
                                apiOkStatuses.includes(Number(msg?.status)) ||
                                loading ||
                                formState.permissionSelected === ""
                            }
                        >
                            {loading && (
                                <span className="loading loading-spinner loading-md"></span>
                            )}
                            {modalType.charAt(0).toUpperCase() +
                                modalType.slice(1)}{" "}
                            Role
                        </button>
                    </div>
                </form>
            </Modal>
        </>
    );
};

export default AddRoleModal;
