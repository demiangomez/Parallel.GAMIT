import { useEffect, useState } from "react";
import { useAuth, useApi } from "../../hooks/";
import { mergePeopleService } from "@services";
import { People, Errors } from "@types";
import { Spinner, Modal, Alert } from "@componentsReact";
import { ArrowRightIcon } from "@heroicons/react/24/outline";

interface MergePeopleModalProps {
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
    handleCloseModal: () => void;
    body: People[] | undefined;
}

const MergePeopleModal = ({
    setStateModal,
    handleCloseModal,
    body,
}: MergePeopleModalProps) => {
    const [loading, setLoading] = useState<boolean>(false);

    const [successText, setSuccessText] = useState<boolean>(false);

    const [people, setPeople] = useState<string[] | undefined>(undefined);

    const [from, setFrom] = useState<string | undefined>(undefined);

    const [to, setTo] = useState<string | undefined>(undefined);

    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const getFullName = (name: string, surname: string) => {
        return `${name} ${surname}`;
    };

    const findPerson = (name: string) => {
        const foundPerson = body?.find((person) => {
            if (person) {
                return (
                    getFullName(person.first_name, person.last_name) === name
                );
            }
            return false;
        });
        return foundPerson;
    };

    const mergePeople = async () => {
        try {
            setLoading(true);
            if (from !== undefined && to !== undefined) {
                if (from && to) {
                    const fromPerson = findPerson(from);
                    const toPerson = findPerson(to);
                    if (fromPerson !== undefined && toPerson !== undefined) {
                        await mergePeopleService(api, {
                            from: fromPerson?.id,
                            to: toPerson?.id,
                        });
                    }
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
            setSuccessText(true);
            setTimeout(() => {
                handleCloseModal();
            }, 2000);
        }
    };

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        mergePeople();
    };

    const filterPeople = (people: People[]) => {
        const filteredPeople = people.map((person) => {
            if (person) {
                return getFullName(person.first_name, person.last_name);
            }
        });
        return filteredPeople;
    };

    useEffect(() => {
        if (body && body.length > 0) {
            const filteredPeople = filterPeople(body).filter(
                (person): person is string => person !== undefined,
            );
            filteredPeople.sort((a, b) => a.localeCompare(b));
            setPeople(filteredPeople);
        }
    }, [body]);

    return (
        <Modal
            close={false}
            modalId={"MergePeople"}
            size={"smPlus"}
            handleCloseModal={() => handleCloseModal()}
            setModalState={setStateModal}
            noPadding={true}
        >
            {" "}
            
            <div
                className={
                    successText
                        ? "flex flex-col items-start justify-between max-h-[56vh] min-w-[40vw] gap-0"
                        : from == to && from !== undefined && to !== undefined
                          ? "flex flex-col items-start justify-between max-h-[56vh] min-w-[40vw] gap-0"
                          : "flex flex-col items-start justify-start max-h-[56vh] min-w-[40vw] gap-0 pb-4"
                }
            >
                <div className="w-full border-b-2 border-gray-300 pb-6 pl-8 pt-6">
                    <h1 className="text-2xl font-bold">Merge People</h1>
                </div>
                {
                <form
                    typeof="submit"
                    onSubmit={(e) => {
                        handleSubmit(e);
                    }}
                    className="w-full flex justify-start items-center flex-col gap-4"
                >
                    <div className="flex justify-start flex-row items-center border-b-2 mt-4 border-gray-300 w-full pb-6">
                        <div className="flex flex-col gap-6 w-full max-w-[500px] pl-6">
                            <h2 className="text-xl font-semibold">
                                Merge From:
                            </h2>
                            <div className="max-h-[20vh] overflow-y-auto">
                                {people?.map((person, index) => (
                                    <div
                                        key={index}
                                        className="flex flex-row gap-4 p-2 mb-1 hover:bg-gray-200 rounded-md"
                                    >
                                        <input
                                            className="checkbox"
                                            type="checkbox"
                                            name="person"
                                            value={person}
                                            checked={from === person}
                                            onChange={() =>
                                                from === person
                                                    ? setFrom(undefined)
                                                    : setFrom(person)
                                            }
                                        />
                                        <label
                                            htmlFor="person"
                                            className="text-xl"
                                        >
                                            {person}
                                        </label>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div className="flex flex-col gap-6 w-full max-w-[500px] pl-6">
                            <h2 className="text-xl font-semibold">Merge To:</h2>
                            <div className="max-h-[20vh] overflow-y-auto">
                                {people?.map((person, index) => (
                                    <div
                                        key={index}
                                        className="flex flex-row justify-start items-center gap-4 p-2 mb-1 hover:bg-gray-200 rounded-md"
                                    >
                                        <input
                                            className="checkbox"
                                            type="checkbox"
                                            name="person"
                                            value={person}
                                            checked={to === person}
                                            onChange={() =>
                                                to === person
                                                    ? setTo(undefined)
                                                    : setTo(person)
                                            }
                                        />
                                        <label
                                            htmlFor="person"
                                            className="text-xl"
                                        >
                                            {person}
                                        </label>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                    <div className="flex justify-center flex-col w-full items-center gap-1">
                        <button
                            disabled={
                                !(to && from) || to === from || successText
                            }
                            className="btn btn-neutral w-32"
                            type="submit"
                        >
                            {loading && <Spinner size="lg" />}
                            {!loading && (
                                <div className="flex justify-center items-center gap-1">
                                    <p className="font-semibold text-base">
                                        Merge
                                    </p>
                                    <ArrowRightIcon className="size-5" />
                                </div>
                            )}
                        </button>
                    </div>
                </form>
                }
                {successText ? (
                    <div className="w-full p-4">
                        <Alert
                            msg={{
                                status: 200,
                                msg: "!Merge successfully done!",
                            }}
                        />
                    </div>
                ) : to === from &&
                  to !== undefined &&
                  from !== undefined &&
                  !successText ? (
                    <div className="w-full p-4">
                        <Alert
                            msg={{
                                status: 400,
                                msg: "¡Merge same person is not possible!",
                                errors: {
                                    errors: [
                                        {
                                            code: "400",
                                            detail: "",
                                            attr: "merge",
                                        },
                                    ],
                                    type: "MergeError",
                                } as Errors,
                            }}
                        />
                    </div>
                ) : null}
                
            </div>
        </Modal>
    );
};

export default MergePeopleModal;
