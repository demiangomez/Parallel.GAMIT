//Componentes
import Alert from "@components/Alert";
import ImageUploadCircle from "@components/ImageUploadCircle";

//Iconos
import { PencilSquareIcon } from "@heroicons/react/24/outline";

//Hooks
import { useApi, useAuth, useFormReducer } from "@hooks/index";

//Hooks de React
import { useEffect, useState } from "react";

//Fetchs
import { getUsersService, patchPeopleService } from "@services";

//Interfaces
import {
    Errors,
    ErrorResponse,
    ExtendedPeople,
    People,
    UsersData,
    UsersServiceData,
} from "@types";

//Reducer Form States
import { USERS_STATE } from "@utils/reducerFormStates";
import { Menu, MenuButton, MenuContent } from "@components/index";

type Props = {
    person: People | null;
};

const PeopleSettingsForm = ({ person }: Props) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);
    const { formState, dispatch } = useFormReducer(USERS_STATE);

    const [users, setUsers] = useState<UsersData[]>([]);
    const [image, setImagen] = useState<string | null>(null);
    const [initialValue, setInitialValue] = useState<People | null>(null);

    const [edit, setEdit] = useState<boolean>(false);
    const [saved, setSaved] = useState<boolean>(false);
    const [loading, setLoading] = useState<boolean>(false);
    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);
    const [matchingUsers, setMatchingUsers] = useState<UsersData[] | undefined>(
        undefined,
    );
    const [showMenu, setShowMenu] = useState<
        { type: string; show: boolean } | undefined
    >(undefined);

    const getUsers = async () => {
        try {
            const res = await getUsersService<UsersServiceData>(api);
            setUsers(res.data);
        } catch (err) {
            console.error(err);
        }
    };

    const getPeopleData = () => {
        const extendedUser = {
            id: person?.id ?? 0,
            photo_actual_file: person?.photo_actual_file ?? "",
            user_name: person?.user_name ?? "",
            last_name: person?.last_name ?? "",
            first_name: person?.first_name ?? "",
            email: person?.email ?? "",
            phone: person?.phone ?? "",
            address: person?.address ?? "",
            institution: person?.institution ?? "",
            position: person?.position ?? "",
            user: person?.user ?? "",
        };

        setInitialValue(extendedUser);
        dispatch({
            type: "set",
            payload: extendedUser,
        });
    };

    const patchPerson = async () => {
        try {
            setLoading(true);

            const { id, photo_actual_file, ...data } = formState; // eslint-disable-line

            const formData = new FormData();

            Object.keys(data).forEach((key) => {
                formData.append(key, data[key as keyof typeof data]);
            });

            // Manejar la imagen de forma especial
            if (image) {
                // Convertir base64 a File si es necesario
                const response = await fetch(image);
                const blob = await response.blob();
                const file = new File([blob], "profile-photo.jpg", {
                    type: "image/jpeg",
                });
                formData.append("photo", file);
            } else {
                formData.append("photo_actual_file", photo_actual_file);
            }

            const res = await patchPeopleService<
                ExtendedPeople | ErrorResponse
            >(api, Number(person?.id), formData);
            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setMsg({
                    status: res.statusCode,
                    msg: "Person edited successfully",
                });
                setSaved(true);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
            setTimeout(() => {
                window.location.reload();
            }, 100);
        }
    };

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        patchPerson();
    };

    const handleChange = (e: HTMLInputElement | HTMLSelectElement) => {
        const { name, value } = e;

        const alterValue = () => {
            switch (value) {
                case "true":
                    return true;
                case "false":
                    return false;
                default:
                    return value;
            }
        };

        if (name === "user_name") {
            const match = users?.filter((u) =>
                u.username.toLowerCase().includes(value.toLowerCase()),
            );
            setMatchingUsers(match);
            setShowMenu({
                type: name,
                show: true,
            });
        }

        dispatch({
            type: "change_value",
            payload: {
                inputName: name,
                inputValue: alterValue(),
            },
        });
    };

    useEffect(() => {
        getPeopleData();
        getUsers();
    }, []);

    useEffect(() => {
        if (!image) return;
        dispatch({
            type: "change_value",
            payload: {
                inputName: "photo_actual_file",
                inputValue: image,
            },
        });
    }, [image]);

    return (
        <>
            <body className="self-center w-full flex flex-col justify-center min-h-[50vh]">
                <div className="bg-base-200 p-7 mt-3 rounded-md align-middle">
                    <header className="flex justify-between">
                        <h2 className="text-2xl font-bold my-6">
                            Associated person
                        </h2>
                        <button
                            className="flex btn btn-ghost btn-circle self-center"
                            onClick={() => {
                                if (edit && initialValue && !saved) {
                                    dispatch({
                                        type: "set",
                                        payload: initialValue,
                                    });
                                    setImagen(null);
                                }
                                setEdit(!edit);
                                setMsg(undefined);
                            }}
                        >
                            <PencilSquareIcon title="edit" className="size-8" />
                        </button>
                    </header>
                    <form
                        className=" flex flex-col items-center justify-center w-full gap-4 mb-3"
                        onSubmit={(e: React.FormEvent<HTMLFormElement>) =>
                            handleSubmit(e)
                        }
                    >
                        <ImageUploadCircle
                            edit={edit}
                            image={
                                !edit
                                    ? saved
                                        ? formState.photo_actual_file ||
                                          undefined
                                        : initialValue?.photo_actual_file ||
                                          undefined
                                    : image ||
                                      formState.photo_actual_file ||
                                      undefined
                            }
                            setImage={setImagen}
                        />
                        <div className="w-full grid grid-cols-2 gap-2">
                            {Object.keys(formState).map((key) => {
                                const notShow = [
                                    "id",
                                    "position",
                                    "photo_actual_file",
                                    "user",
                                ];

                                if (!notShow.includes(key))
                                    return (
                                        <>
                                            <label
                                                className={`w-full input input-bordered flex items-center col-span-2`}
                                            >
                                                <span className="font-bold p-2 w-fit">
                                                    {key === "user_name"
                                                        ? "USER"
                                                        : key
                                                              .toUpperCase()
                                                              .replace("_", " ")
                                                              .replace(
                                                                  "_",
                                                                  " ",
                                                              )}
                                                </span>

                                                <input
                                                    name={key}
                                                    className="grow truncate min-w-[0]"
                                                    readOnly={!edit}
                                                    autoComplete={"off"}
                                                    onChange={(e) => {
                                                        handleChange(e.target);
                                                    }}
                                                    value={formState[key] ?? ""}
                                                    type={"text"}
                                                    onClick={(e) => {
                                                        if (
                                                            edit &&
                                                            key === "user_name"
                                                        ) {
                                                            handleChange(
                                                                e.target as HTMLInputElement,
                                                            );
                                                            setShowMenu({
                                                                type: key,
                                                                show: true,
                                                            });
                                                        } else {
                                                            setShowMenu({
                                                                type: key,
                                                                show: false,
                                                            });
                                                        }
                                                    }}
                                                />
                                                {key === "user_name" &&
                                                    edit && (
                                                        <MenuButton
                                                            setShowMenu={
                                                                setShowMenu
                                                            }
                                                            showMenu={showMenu}
                                                            typeKey={key}
                                                        />
                                                    )}
                                            </label>

                                            {showMenu?.show &&
                                            showMenu.type === key &&
                                            key === "user_name" ? (
                                                <div className="col-span-2">
                                                    <Menu>
                                                        {(matchingUsers &&
                                                        matchingUsers.length > 0
                                                            ? matchingUsers
                                                            : users
                                                        )?.map((u) => (
                                                            <MenuContent
                                                                key={u.id}
                                                                typeKey={"user"}
                                                                value={
                                                                    u.username
                                                                }
                                                                alterValue={u.id?.toString()}
                                                                alterFunction={() => {
                                                                    dispatch({
                                                                        type: "change_value",
                                                                        payload:
                                                                            {
                                                                                inputName:
                                                                                    "user",
                                                                                inputValue:
                                                                                    u.id ??
                                                                                    0,
                                                                            },
                                                                    });
                                                                    dispatch({
                                                                        type: "change_value",
                                                                        payload:
                                                                            {
                                                                                inputName:
                                                                                    "user_name",
                                                                                inputValue:
                                                                                    u.username ??
                                                                                    "",
                                                                            },
                                                                    });
                                                                    setShowMenu(
                                                                        undefined,
                                                                    );
                                                                }}
                                                                setShowMenu={
                                                                    setShowMenu
                                                                }
                                                            />
                                                        ))}
                                                    </Menu>
                                                </div>
                                            ) : null}
                                        </>
                                    );
                            })}
                            <div className="col-span-2 flex justify-center">
                                {edit && (
                                    <button
                                        className="w-36 btn btn-success rounded my-2"
                                        disabled={loading}
                                    >
                                        {loading && (
                                            <span className="loading loading-spinner loading-md"></span>
                                        )}
                                        UPDATE
                                    </button>
                                )}
                            </div>
                        </div>
                    </form>
                    <Alert msg={msg} />
                </div>
            </body>
        </>
    );
};

export default PeopleSettingsForm;
