//Componentes
import { Alert, ImageUploadCircle, Slider } from "@componentsReact";

//Iconos
import {
    EyeIcon,
    EyeSlashIcon,
    PencilSquareIcon,
} from "@heroicons/react/24/outline";

//Hooks
import { useApi, useAuth, useFormReducer } from "@hooks";

//Hooks de React
import { useEffect, useState } from "react";

//Fetchs
import { getRolesService, patchUserService, getUserService } from "@services";

//Interfaces
import {
    User,
    Role,
    Errors,
    UsersData,
    ErrorResponse,
    RolesServiceData,
} from "@types";

//Reducer Form States
import { USERS_STATE } from "@utils/reducerFormStates";

//Utils
// import { jwtDeserializer } from "@utils/index";

type Props = {
    userData: UsersData | null;
};

const UserSettingsForm = ({ userData }: Props) => {
    const { formState, dispatch } = useFormReducer(USERS_STATE);
    const [initialValue, setInitialValue] = useState<UsersData>(
        USERS_STATE as UsersData,
    );
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [roles, setRoles] = useState<Role[]>([]);
    const [image, setImagen] = useState<string | null>(null);
    const [edit, setEdit] = useState<boolean>(false);
    const [saved, setSaved] = useState<boolean>(false);
    const [seePwd, setSeePwd] = useState<boolean>(false);
    const [loading, setLoading] = useState<boolean>(false);
    const [msg, setMsg] = useState<
        { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const getRoles = async () => {
        try {
            const res = await getRolesService<RolesServiceData>(api);
            setRoles(res.data);
        } catch (err) {
            console.error(err);
        }
    };

    const fetchUser = async (id?: number) => {
        try {
            const userId = id ?? Number(formState.id);
            if (!userId) return;
            const res = await getUserService<UsersData>(api, userId);
            if (res) {
                const user = res;
                const newInitial = {
                    id: user.id,
                    username: user.username,
                    password: user.password,
                    first_name: user.first_name,
                    last_name: user.last_name,
                    role: {
                        id: user.role.id,
                        name: user.role.name,
                    },
                    is_active: user.is_active,
                    email: user.email,
                    phone: user.phone,
                    address: user.address,
                    photo: user.photo,
                    clustering_distance: user.clustering_distance,
                };

                setInitialValue(newInitial);
                dispatch({ type: "set", payload: newInitial });
                setImagen(null);
            }
        } catch (err) {
            console.error(err);
        }
    };

    //with_people
    const putUser = async () => {
        try {
            setLoading(true);

            const formData = new FormData();

            const { role, photo, ...rest } = formState;

            Object.keys(rest).forEach((key) => {
                formData.append(key, rest[key]);
            });

            formData.append("role", String(role.id));

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
                formData.append("photo_actual_file", photo);
            }

            const res = await patchUserService<User | ErrorResponse>(
                api,
                Number(formState.id),
                formData,
            );
            if (res) {
                if ("status" in res) {
                    setMsg({
                        status: res.statusCode,
                        msg: res.response.type,
                        errors: res.response,
                    });
                } else {
                    setMsg({
                        status: 200,
                        msg: "User updated successfully",
                    });
                    setSaved(true);
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            try {
                await fetchUser();
            } catch (err) {
                console.error("Error refetching user after update:", err);
            }
            setLoading(false);
            setTimeout(() => {
                window.location.reload();
            }, 100);
        }
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

        dispatch({
            type: "change_value",
            payload: {
                inputName: name,
                inputValue: alterValue(),
            },
        });
    };

    useEffect(() => {
        if (userData) {
            const initialValue = {
                id: userData.id,
                username: userData.username,
                password: userData.password,
                first_name: userData.first_name,
                last_name: userData.last_name,
                role: {
                    id: userData.role.id,
                    name: userData.role.name,
                },
                is_active: userData.is_active,

                email: userData.email,
                phone: userData.phone,
                address: userData.address,
                photo: userData.photo,
                clustering_distance: userData.clustering_distance,
            };

            setInitialValue(initialValue);

            dispatch({
                type: "set",
                payload: initialValue,
            });
        }
    }, []);

    useEffect(() => {
        getRoles();
    }, []);

    useEffect(() => {
        if (!image) return;
        dispatch({
            type: "change_value",
            payload: {
                inputName: "photo",
                inputValue: image,
            },
        });
    }, [image]);

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        putUser();
    };

    return (
        <>
            <body className="w-full flex flex-col justify-center min-h-[50vh]">
                <div className="bg-base-200 p-7 rounded-md align-middle">
                    <header className="flex justify-between">
                        <h2 className="text-2xl font-bold my-6">User</h2>
                        <button
                            className="flex btn btn-ghost btn-circle self-center"
                            onClick={() => {
                                if (edit && !saved) {
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
                        onSubmit={(e: React.FormEvent<HTMLFormElement>) => {
                            handleSubmit(e);
                        }}
                    >
                        <ImageUploadCircle
                            edit={edit}
                            image={
                                !edit
                                    ? saved
                                        ? (formState.photo ?? null)
                                        : (initialValue.photo ?? null)
                                    : (image ?? formState.photo)
                            }
                            setImage={setImagen}
                        />
                        <div className="w-full grid grid-cols-2 gap-2">
                            {Object.keys(formState).map((key) => {
                                const notShow = ["photo", "id", "is_active"];
                                const doubleRow = [
                                    "first_name",
                                    "last_name",
                                    "role",
                                    "email",
                                    "phone",
                                    "address",
                                    "clustering_distance",
                                ];

                                if (!notShow.includes(key))
                                    return (
                                        <>
                                            {key === "role" ? (
                                                <select
                                                    name={
                                                        key === "role"
                                                            ? "role.id"
                                                            : key
                                                    }
                                                    className={`select select-bordered w-full text-center font-bold col-span-${doubleRow.includes(key) ? "2" : "1"}`}
                                                    disabled={!edit}
                                                    onChange={(e) => {
                                                        handleChange(e.target);
                                                    }}
                                                    value={
                                                        key === "role" &&
                                                        formState.role.id
                                                            ? formState.role.id
                                                            : ""
                                                    }
                                                >
                                                    <option disabled value="">
                                                        Select a role
                                                    </option>

                                                    {roles?.map((role) => (
                                                        <option value={role.id}>
                                                            {role.name.toUpperCase()}
                                                        </option>
                                                    ))}
                                                </select>
                                            ) : key ===
                                              "clustering_distance" ? (
                                                <>
                                                    <Slider
                                                        tittle="CLUSTERING"
                                                        minValue={0}
                                                        maxValue={20}
                                                        name={key}
                                                        disabled={!edit}
                                                        classContainer="my-2 w-full col-span-2"
                                                        value={
                                                            formState[key] ?? 0
                                                        }
                                                        suffixValue="Mts"
                                                        onChange={(e) =>
                                                            handleChange(
                                                                e.target,
                                                            )
                                                        }
                                                    />
                                                </>
                                            ) : (
                                                <label
                                                    className={`w-full input input-bordered flex items-center sm:col-span-2 xs:col-span-2 col-span-${doubleRow.includes(key) ? "2" : "1"}`}
                                                >
                                                    <span className="font-bold p-2 w-fit">
                                                        {key
                                                            .toUpperCase()
                                                            .replace("_", " ")
                                                            .replace("_", " ")}
                                                    </span>
                                                    <input
                                                        name={key}
                                                        className="grow truncate min-w-[0]"
                                                        readOnly={!edit}
                                                        autoComplete={
                                                            key === "password"
                                                                ? "new-password"
                                                                : "off"
                                                        }
                                                        onChange={(e) => {
                                                            handleChange(
                                                                e.target,
                                                            );
                                                        }}
                                                        value={
                                                            formState[key] ?? ""
                                                        }
                                                        type={
                                                            key ===
                                                                "password" &&
                                                            !seePwd
                                                                ? "password"
                                                                : "text"
                                                        }
                                                        placeholder={
                                                            key === "password"
                                                                ? "********"
                                                                : ""
                                                        }
                                                    />
                                                    {key === "password" &&
                                                    edit ? (
                                                        !seePwd ? (
                                                            <EyeSlashIcon
                                                                className="size-6 cursor-pointer"
                                                                onClick={() =>
                                                                    setSeePwd(
                                                                        !seePwd,
                                                                    )
                                                                }
                                                            />
                                                        ) : (
                                                            <EyeIcon
                                                                className="size-6 cursor-pointer"
                                                                onClick={() =>
                                                                    setSeePwd(
                                                                        !seePwd,
                                                                    )
                                                                }
                                                            />
                                                        )
                                                    ) : null}
                                                </label>
                                            )}
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

export default UserSettingsForm;
