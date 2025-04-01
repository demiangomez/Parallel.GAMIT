import { useLocation, useParams } from "react-router-dom";
import { PdfContainer } from "@componentsReact";

import {
    ArrowPathIcon,
    ExclamationCircleIcon,
} from "@heroicons/react/24/outline";

import { hasDifferences } from "@utils";
import {
    Errors,
    StationData,
    StationMetadataServiceData,
    StationVisitsData,
} from "@types";

interface Props {
    functions: {
        setMessage: React.Dispatch<
            React.SetStateAction<{
                error: boolean | undefined;
                msg: string;
                errors?: Errors;
            }>
        >;
        setLoadPdf: React.Dispatch<React.SetStateAction<boolean>>;
        setLoadedPdfData: React.Dispatch<
            React.SetStateAction<boolean | undefined>
        >;
        getButtonClasses: () => string;
        getKmzBalloon: () => void;
        getReStation: () => void;
    };
    constants: {
        station: StationData | undefined;
        reLoading: boolean;
        reStation: StationData | undefined;
        stationMeta: StationMetadataServiceData | undefined;
        visits: StationVisitsData[] | undefined;
        loadPdf: boolean;
        loadedMap: boolean | undefined;
        errorMessages: string[];
        stationLocationScreen: string;
        stationLocationDetailScreen: string;
    };
}

const StationButtons = ({ functions, constants }: Props) => {
    const { nc, sc } = useParams();

    const location = useLocation();

    const {
        setMessage,
        setLoadPdf,
        setLoadedPdfData,
        getButtonClasses,
        getKmzBalloon,
        getReStation,
    } = functions;

    const {
        station,
        reLoading,
        reStation,
        stationMeta,
        visits,
        loadPdf,
        loadedMap,
        errorMessages,
        stationLocationScreen,
        stationLocationDetailScreen,
    } = constants;

    const definitiveStation =
        station && reStation && hasDifferences(station, reStation)
            ? reStation
            : station;

    return (
        <div className="flex items-center justify-start min-w-[100px] gap-0 absolute -right-[105px] top-3">
            {location.pathname === `/${nc}/${sc}` && (
                <>
                    <PdfContainer
                        station={definitiveStation}
                        stationMeta={stationMeta}
                        visits={visits}
                        loadPdf={loadPdf}
                        stationLocationScreen={stationLocationScreen}
                        stationLocationDetailScreen={
                            stationLocationDetailScreen
                        }
                        loadedMap={loadedMap}
                        // loadPdfdata={loadPdfData}
                        setMessage={setMessage}
                        setLoadPdf={setLoadPdf}
                        setLoadedPdfData={setLoadedPdfData}
                    />

                    <button
                        className={
                            "flex items-center justify-center " +
                            getButtonClasses()
                        }
                        title="Download station kmz"
                        onClick={(e) => {
                            e.preventDefault();
                            getKmzBalloon();
                        }}
                    >
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={1.5}
                            stroke="currentColor"
                            className="size-6"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M12.75 3.03v.568c0 .334.148.65.405.864l1.068.89c.442.369.535 1.01.216 1.49l-.51.766a2.25 2.25 0 0 1-1.161.886l-.143.048a1.107 1.107 0 0 0-.57 1.664c.369.555.169 1.307-.427 1.605L9 13.125l.423 1.059a.956.956 0 0 1-1.652.928l-.679-.906a1.125 1.125 0 0 0-1.906.172L4.5 15.75l-.612.153M12.75 3.031a9 9 0 0 0-8.862 12.872M12.75 3.031a9 9 0 0 1 6.69 14.036m0 0-.177-.529A2.25 2.25 0 0 0 17.128 15H16.5l-.324-.324a1.453 1.453 0 0 0-2.328.377l-.036.073a1.586 1.586 0 0 1-.982.816l-.99.282c-.55.157-.894.702-.8 1.267l.073.438c.08.474.49.821.97.821.846 0 1.598.542 1.865 1.345l.215.643m5.276-3.67a9.012 9.012 0 0 1-5.276 3.67m0 0a9 9 0 0 1-10.275-4.835M15.75 9c0 .896-.393 1.7-1.016 2.25"
                            />
                        </svg>
                    </button>
                </>
            )}

            {location.pathname === `/${nc}/${sc}/rinex` &&
                errorMessages.length > 0 && (
                    <div className="indicator">
                        <ExclamationCircleIcon
                            className={`size-6 fill-red-500`}
                            title={errorMessages.join("\n")}
                        />
                    </div>
                )}
            <button
                className={getButtonClasses()}
                disabled={reLoading}
                onClick={getReStation}
                title="Fetch gaps status"
            >
                <ArrowPathIcon className="size-6" />
            </button>
        </div>
    );
};

export default StationButtons;
