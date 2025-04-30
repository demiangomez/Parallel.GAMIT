import { Alert, Modal, Spinner } from "@components/index";
import { ArrowRightIcon } from "@heroicons/react/24/outline";
import { mergeSourcesServersService } from "@services";
import { Errors, SourcesServerData, ErrorResponse } from "@types";
import { AxiosInstance } from "axios";
import { useState } from "react";

interface SourcesServersMergeModalProps {
    sourcesServers: SourcesServerData[] | undefined;
    handleCloseModal: () => void;
    refetch: () => void;
    api: AxiosInstance;
}

const SourcesServersMergeModal = ({
    sourcesServers,
    handleCloseModal,
    refetch,
    api,
}: SourcesServersMergeModalProps) => {
    const [from, setFrom] = useState<number | undefined>(undefined);

    const [to, setTo] = useState<number | undefined>(undefined);

    const [loading, setLoading] = useState<boolean>(false);

    const [successText, setSuccessText] = useState<boolean>(false);

    const mergeSourcesServers = async () => {
        try {
            setLoading(true);
            const res = await mergeSourcesServersService<ErrorResponse>(api, {
                from: from as number,
                to: to as number,
            });
            if (res.statusCode === 200) {
                setSuccessText(true);
            } else {
                setSuccessText(false);
            }
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = (e: any) => {
        e.preventDefault();
        if (from && to && from !== to) {
            mergeSourcesServers();
        }
    };

    return (
        <Modal
            close={false}
            size="md"
            handleCloseModal={() => {
                handleCloseModal();
                setTo(undefined);
                setFrom(undefined);
                successText && refetch();
            }}
            modalId="Merge Source Server"
        >
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
                    <h1 className="text-2xl font-bold">
                        Transfer Stations
                    </h1>
                </div>
                <form
                    typeof="submit"
                    onSubmit={(e) => {
                        handleSubmit(e);
                    }}
                    className="flex flex-col items-center gap-4 w-full"
                >
                    <div className="grid grid-cols-2 gap-2 grid-flow-col-dense items-center mt-4 w-full">
                        <div className="flex flex-col gap-6 w-full">
                            <h2 className="text-xl font-semibold">
                                Transfer From:
                            </h2>
                            <div className="max-h-[20vh] flex flex-col w-full gap-2 overflow-y-auto">
                                {sourcesServers?.map((s, index) => (
                                <div
                                    key={index}
                                    className="flex justify-center items-center gap-4 p-2 mb-1 hover:bg-gray-400 rounded-md bg-gray-300"
                                >
                                    <input
                                        className="checkbox checkbox-lg"
                                        type="checkbox"
                                        name="person"
                                        value={s.server_id}
                                        checked={from === s.server_id}
                                        onChange={() =>
                                            to === s.server_id
                                                ? setFrom(undefined)
                                                : setFrom(s.server_id)
                                        }
                                    />
                                    <div className="flex flex-col justify-start items-start w-full">
                                        <div className="flex flex-row justify-start items-start w-full">
                                            <label
                                                title={s.fqdn}
                                                className="text-2xl w-3/4 text-pretty truncate"
                                            >
                                                {s.fqdn}
                                            </label>
                                            <label className="text-lg w-1/4 font-bold text-center">
                                                {s.protocol}
                                            </label>
                                        </div>
                                        <label className="w-full overflow-auto whitespace-normal break-all">
                                            {s.path}
                                        </label>
                                        <label>
                                            {s.format}
                                        </label>
                                    </div>
                                </div>
                                ))}
                            </div>
                        </div>
                        <div className="flex flex-col gap-6 w-full">
                            <h2 className="text-xl font-semibold">Transfer To:</h2>
                            <div className="max-h-[20vh] flex flex-col gap-2 overflow-y-auto">
                                {sourcesServers?.map((s, index) => {
                                    return (
                                        <div
                                            key={index}
                                            className="flex justify-center items-center gap-4 p-2 mb-1 hover:bg-gray-400 rounded-md bg-gray-300"
                                        >
                                            <input
                                                className="checkbox checkbox-lg"
                                                type="checkbox"
                                                name="person"
                                                value={s.server_id}
                                                checked={to === s.server_id}
                                                onChange={() =>
                                                    to === s.server_id
                                                        ? setTo(undefined)
                                                        : setTo(s.server_id)
                                                }
                                            />
                                            <div className="flex flex-col justify-start items-start w-full">
                                                <div className="flex flex-row justify-start items-start w-full">
                                                    <label
                                                        title={s.fqdn}
                                                        className="text-2xl w-3/4 text-pretty truncate"
                                                    >
                                                        {s.fqdn}
                                                    </label>
                                                    <label className="text-lg w-1/4 font-bold text-center">
                                                        {s.protocol}
                                                    </label>
                                                </div>
                                                <label>
                                                    {s.format}
                                                </label>
                                                <label className="w-full overflow-auto whitespace-normal break-all">
                                                    {s.path}
                                                </label>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>

                    <div className="flex justify-center flex-col items-center gap-1">
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
                                        Transfer
                                    </p>
                                    <ArrowRightIcon className="size-5" />
                                </div>
                            )}
                        </button>
                    </div>
                </form>
                {successText ? (
                    <div className="w-full p-4">
                        <Alert
                            msg={{
                                status: 200,
                                msg: "!Transfer successfully done!",
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
                                msg: "Transfer same source station order is not possible!",
                                errors: {
                                    errors: [
                                        {
                                            code: "400",
                                            detail: "",
                                            attr: "transfer",
                                        },
                                    ],
                                    type: "TransferError",
                                } as Errors,
                            }}
                        />
                    </div>
                ) : null}
            </div>
        </Modal>
    );
};

export default SourcesServersMergeModal;
