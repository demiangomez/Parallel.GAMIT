import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { StationInfoModal, StationMetadataModal } from "@componentsReact";

import {
    CodeBracketIcon,
    DocumentTextIcon,
    InformationCircleIcon,
    PaperAirplaneIcon,
    UsersIcon,
} from "@heroicons/react/24/outline";

import { StationData, StationMetadataServiceData } from "@types";
import { showModal } from "@utils";

interface SidebarProps {
    show: boolean;
    station: StationData | undefined;
    stationMeta?: StationMetadataServiceData | undefined;
    refetchStationMeta?: () => void;
    refetch?: () => void;
    setShow: React.Dispatch<React.SetStateAction<boolean>>;
}

interface Icons {
    [key: string]: any;
}

const Sidebar = ({
    show,
    station,
    stationMeta,
    refetchStationMeta,
    refetch,
    setShow,
}: SidebarProps) => {
    const navigate = useNavigate();

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const icons: Icons = {
        Information: InformationCircleIcon,
        Metadata: CodeBracketIcon,
        Visits: PaperAirplaneIcon,
        Rinex: DocumentTextIcon,
        People: UsersIcon,
    };

    // const longTitles = ["Information", "Metadata", "Visits", "People"];
    const longTitles = ["Information", "Metadata", "Visits", "Rinex", "People"];

    // const stationPages = ["People", "Visits"];
    const stationPages = ["People", "Visits", "Rinex"];

    // const admTitles = ["Admin", "Users", "Settings"];
    const sidebarWidth = show ? "w-72" : "w-32";

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    return (
        <>
            {
                /*userRole === "1" && AGREGAR SI VAMOS A HANDLEAR X ROLE */ station && (
                    <div
                        className="left-0 top-0 pt-[8vh] bg-gray-800"
                        style={{ minHeight: `calc(100vh - 8vh)` }}
                        onMouseEnter={() => setShow(true)}
                        onMouseLeave={() => setShow(false)}
                    >
                        <div className="flex sm:flex-row sm:justify-around">
                            <div
                                className={
                                    sidebarWidth +
                                    " transition-all duration-200"
                                }
                            >
                                <nav className="mt-10 space-y-8 flex flex-col items-center text-center">
                                    {longTitles.map((title, idx) => (
                                        <div
                                            className="flex w-full justify-center mt-20"
                                            key={idx}
                                        >
                                            <div className="flex items-center justify-center w-4/12 ">
                                                {icons[title] &&
                                                    React.createElement(
                                                        icons[title],
                                                        {
                                                            className: `h-8 w-full ${show ? "ml-16" : ""} text-white mt-2`,
                                                        },
                                                    )}
                                            </div>

                                            {show && station && (
                                                <div className="flex items-center justify-center w-8/12">
                                                    <button
                                                        className="py-2 w-8/12 self-center flex items-center 
                                                transition-colors hover:text-white hover:bg-gray-600 duration-200  
                                                text-gray-400 rounded-lg justify-center"
                                                        key={title + idx}
                                                        onClick={() => {
                                                            stationPages.includes(
                                                                title,
                                                            )
                                                                ? navigate(
                                                                      `/${station.network_code}/${station.station_code}/${title.toLowerCase()}`,
                                                                  )
                                                                : setModals({
                                                                      show: true,
                                                                      title: title,
                                                                      type: "none",
                                                                  });
                                                        }}
                                                    >
                                                        <span className="mx-4 text-lg font-normal">
                                                            {title}
                                                        </span>
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </nav>
                            </div>
                        </div>
                    </div>
                )
            }
            {modals?.show && modals.title === "Information" && (
                <StationInfoModal
                    close={false}
                    station={station}
                    size={"xl"}
                    refetch={refetch ? refetch : () => {}}
                    setModalState={setModals}
                />
            )}
            {modals?.show && modals.title === "Metadata" && (
                <StationMetadataModal
                    close={false}
                    station={station}
                    stationMeta={stationMeta}
                    size={"xl"}
                    refetchStationMeta={
                        refetchStationMeta ? refetchStationMeta : () => {}
                    }
                    refetch={refetch ? refetch : () => {}}
                    setModalState={setModals}
                />
            )}
        </>
    );
};

export default Sidebar;
