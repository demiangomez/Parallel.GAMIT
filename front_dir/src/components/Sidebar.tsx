import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { StationInfoModal, StationMetadataModal } from "@componentsReact";

import {
    ClipboardDocumentListIcon,
    CodeBracketIcon,
    DocumentTextIcon,
    InformationCircleIcon,
    PaperAirplaneIcon,
    PresentationChartLineIcon,
    UsersIcon,
} from "@heroicons/react/24/outline";

import { GetParams, StationData, StationMetadataServiceData } from "@types";
import { showModal } from "@utils";

interface SidebarProps {
    show: boolean;
    station: StationData | undefined;
    mainParams?: GetParams;
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
    mainParams,
    stationMeta,
    refetch,
    setShow,
}: SidebarProps) => {
    //------------------------------------------------Constantes-----------------------------------------------------
    const icons: Icons = {
        Information: InformationCircleIcon,
        Metadata: CodeBracketIcon,
        "Time Series": PresentationChartLineIcon,
        Rinex: DocumentTextIcon,
        Visits: PaperAirplaneIcon,
        People: UsersIcon,
        Events: ClipboardDocumentListIcon,
    };

    // const longTitles = ["Information", "Metadata", "Visits", "People"];
    const longTitles = [
        "Information",
        "Metadata",
        "Time Series",
        "Rinex",
        "Visits",
        "People",
        "Events",
    ];

    // const stationPages = ["People", "Visits"];
    const stationPages = ["People", "Visits", "Rinex", "Time Series", "Events"];

    // const admTitles = ["Admin", "Users", "Settings"];
    const sidebarWidth = show ? "w-72" : "w-32";
    //-----------------------------------------------UseNavigate-----------------------------------------------------

    const navigate = useNavigate();

    //-----------------------------------------------UseState------------------------------------------------

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    //-----------------------------------------------UseEffect------------------------------------------------
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
                                            className="flex w-full justify-center mt-16"
                                            key={idx}
                                        >
                                            <div className="flex items-center justify-center w-4/12 ">
                                                {icons[title] &&
                                                    React.createElement(
                                                        title === "Time Series"
                                                            ? icons[
                                                                  "Time Series"
                                                              ]
                                                            : icons[title],
                                                        {
                                                            className: `h-8 w-full hover:scale-110 transition-all
                                                             cursor-pointer ${show ? "ml-16" : ""} text-white mt-2 `,
                                                            onClick: () => {
                                                                stationPages.includes(
                                                                    title,
                                                                )
                                                                    ? navigate(
                                                                          `/${station.network_code}/${station.station_code}/${title == "Time Series" ? "timeseries" : title.toLowerCase()}`,
                                                                          {
                                                                              state: {
                                                                                  ...station,
                                                                                  mainParams:
                                                                                      mainParams,
                                                                              },
                                                                          },
                                                                      )
                                                                    : setModals(
                                                                          {
                                                                              show: true,
                                                                              title: title,
                                                                              type: "none",
                                                                          },
                                                                      );
                                                            },
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
                                                                      `/${station.network_code}/${station.station_code}/${title.replace(" ", "").toLowerCase()}`,
                                                                      {
                                                                          state: {
                                                                              ...station,
                                                                              mainParams:
                                                                                  mainParams,
                                                                          },
                                                                      },
                                                                  )
                                                                : setModals({
                                                                      show: true,
                                                                      title: title,
                                                                      type: "none",
                                                                  });
                                                        }}
                                                    >
                                                        <span className="mx-4 text-lg font-normal whitespace-nowrap">
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
                    stationMetaMain={stationMeta}
                    size={"xl"}
                    refetch={refetch ? refetch : () => {}}
                    setModalState={setModals}
                />
            )}
        </>
    );
};

export default Sidebar;
