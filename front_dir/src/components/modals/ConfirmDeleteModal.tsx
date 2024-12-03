import { Alert, Modal } from "@componentsReact";

import { ExclamationTriangleIcon } from "@heroicons/react/24/outline";
import { Errors } from "@types";
import { apiOkStatuses } from "@utils/index";

interface ConfirmDeleteModalProps {
    variant?: "danger" | "warning" | "success";
    mainMsg?: string;
    alterMsg?: string;
    msg?:
        | {
              status: number;
              msg: string;
              errors?: Errors;
          }
        | undefined;
    loading?: boolean;
    confirmRemove: () => void;
    closeModal: () => void;
}

const ConfirmDeleteModal = ({
    variant,
    mainMsg,
    alterMsg,
    msg,
    loading,
    confirmRemove,
    closeModal,
}: ConfirmDeleteModalProps) => {
    const statusMsg = msg?.status;

    return (
        <Modal
            close={false}
            size="sm"
            modalId="ConfirmDelete"
            variant={variant ? variant : "danger"}
            handleCloseModal={() => closeModal()}
        >
            <div className="flex items-center justify-center">
                <div className="w-3/12">
                    <ExclamationTriangleIcon
                        className={`size-20 ${
                            variant && variant === "danger"
                                ? "text-red-500"
                                : variant === "warning"
                                  ? "text-yellow-500"
                                  : "text-red-500"
                        }`}
                    />
                </div>
                <div className="w-9/12 flex flex-col">
                    <span className="text-xl font-bold">Are you sure?</span>
                    <span className="">
                        {mainMsg ??
                            "Are you sure you want to delete this register ?"}

                        {alterMsg}
                    </span>
                </div>
            </div>
            <div className="flex justify-center">
                {msg && <Alert msg={msg} />}
            </div>
            <div className="flex justify-center mt-6 space-x-4">
                <button
                    className="btn btn-error w-4/12"
                    type="button"
                    onClick={() => confirmRemove()}
                    disabled={
                        loading || apiOkStatuses.includes(Number(statusMsg))
                    }
                >
                    Remove{" "}
                    {loading && (
                        <span className="loading loading-spinner loading-sm self-center"></span>
                    )}
                </button>
                <button
                    className="btn btn-secondary w-4/12"
                    type="button"
                    onClick={() => closeModal()}
                >
                    Close
                </button>
            </div>
        </Modal>
    );
};

export default ConfirmDeleteModal;
