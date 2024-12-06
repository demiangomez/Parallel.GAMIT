import { Modal } from "@componentsReact";

import { ClipboardDocumentIcon } from "@heroicons/react/24/outline";

import { StationEvents } from "@types";

import { formatValue } from "@utils";
import { usePopup } from "@hooks";

interface Props {
    event: StationEvents | undefined;
    setStateModal: React.Dispatch<
        React.SetStateAction<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >
    >;
}

const EventsDetail = ({ event, setStateModal }: Props) => {
    const { showPopup, show } = usePopup(2000);

    return (
        <Modal
            close={false}
            modalId={"EventsDetail"}
            size={"lg"}
            setModalState={setStateModal}
        >
            <h1 className="text-center text-2xl font-bold">Event Details</h1>
            <div className="grid grid-cols-3 grid-flow-dense">
                {event &&
                    Object.entries(event).map(([key, value]) => {
                        const keysToIgnore = [
                            "event_id",
                            "network_code",
                            "station_code",
                        ];

                        if (keysToIgnore.includes(key)) return null;

                        return (
                            <div
                                key={key}
                                className={`card bg-base-200 shadow-xl ${key === "description" ? "col-span-3" : ""} m-2 p-3`}
                            >
                                <h2 className="card-title justify-between border-b-2 border-base-300 p-2">
                                    {key.replace(/_/g, " ").toUpperCase()}
                                    {key === "description" && (
                                        <div
                                            className={` ${showPopup ? "tooltip tooltip-open" : ""} mr-2`}
                                            data-tip="Copied !"
                                        >
                                            <ClipboardDocumentIcon
                                                className="size-6 cursor-pointer rounded-md transition-all duration-75 btn-ghost hover:scale-125"
                                                onClick={() => {
                                                    navigator.clipboard.writeText(
                                                        formatValue(
                                                            value,
                                                            false,
                                                        ),
                                                    );
                                                    show();
                                                }}
                                            />
                                        </div>
                                    )}
                                </h2>
                                <div className="card-body font-medium">
                                    <span className="whitespace-pre-wrap">
                                        {formatValue(value, false)}
                                    </span>
                                </div>
                            </div>
                        );
                    })}
            </div>
        </Modal>
    );
};

export default EventsDetail;
