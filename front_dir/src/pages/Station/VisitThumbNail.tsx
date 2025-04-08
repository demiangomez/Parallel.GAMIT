// import { useLocation, useOutletContext } from "react-router-dom";
// import { useEffect, useState } from "react";
import {
    MapVisit,
    Spinner,
} from "@componentsReact";

import {
    StationCampaignsData,
    StationData,
    StationVisitsData,
    StationVisitsFilesData,
} from "@types";

import { Bars3BottomRightIcon, TrashIcon, UserIcon,  DocumentChartBarIcon, DocumentMagnifyingGlassIcon, DocumentIcon} from "@heroicons/react/24/outline";

interface VisitThumbNailProps {
    station: StationData;
    visit: StationVisitsData;
    setModals: React.Dispatch<React.SetStateAction<{ show: boolean; title: string; type: "add" | "edit" | "none" } | undefined>>;
    setVisitToDel: React.Dispatch<React.SetStateAction<number | undefined>>;
    setVisit: React.Dispatch<React.SetStateAction<StationVisitsData | undefined>>;
    campaigns: StationCampaignsData[] | undefined;
    loadingVisitImages: boolean;
    visitImages: StationVisitsFilesData[] | undefined;
    types: { image: string; name: string }[];
    statuses: { name: string; color: string }[];
}


const VisitThumbNail = ({station, visit, setModals, setVisitToDel, setVisit, campaigns, loadingVisitImages, visitImages, types, statuses}:VisitThumbNailProps) => {
    const joinPeople = (people: {id: number, name: string}[]) =>{
        return people.map(person => person.name).join(", ");
    }

    const getObservationFilesString = () =>{return "Observation Files: " + (visit?.observation_file_count ? visit.observation_file_count : "None");}

    const getPeopleString = () =>{return "People: " + (visit?.people && Array.isArray(visit?.people) ? joinPeople(visit.people) : "None");}

    const getOtherFilesString = () =>{return "Other Files: " + (visit?.other_file_count ? visit.other_file_count : "None");}
    
    const getLogSheetFilesString = () =>{return "Logsheet: " + (visit?.log_sheet_filename? visit.log_sheet_filename : "None");}

    return (
        <div
            key={visit.id}
            className="card bg-neutral-content"
        >
            <div className="inline-flex self-end">
            <button
                title={"delete"}
                className="btn btn-ghost btn-circle"
                onClick={() => {
                setModals({
                    show: true,
                    title: "ConfirmDelete",
                    type: "edit",
                });
                setVisitToDel(visit.id);
                }}
            >
                <TrashIcon className="size-8 text-red-600" />
            </button>
            <button
                title={"details"}
                className="btn btn-ghost btn-circle"
                onClick={() => {
                setModals({
                    show: true,
                    title: "VisitDetail",
                    type: "none",
                });
                setVisit(visit);
                }}
            >
                <Bars3BottomRightIcon className="size-8" />
            </button>
            </div>
            <div className="card-body space-y-4 flex flex-col justify-start items-center">
            <h2 className="text-2xl self-center">
                <span className="font-semibold ">
                Visit date{" "}
                </span>
                {visit?.date}
            </h2>
            <span className="self-center text-xl">
                <span className="font-semibold ">
                Campaign{" "}
                </span>
                {visit?.campaign
                ? campaigns?.find(
                    (c) =>
                        c.id ===
                        Number(
                        visit.campaign,
                        ),
                    )?.name
                : "N/A"}
            </span>
            <div className="flex flex-row space-x-4">
                <div className="tooltip" 
                data-tip={getPeopleString()}>
                <UserIcon id="PersonsIcon" className="size-8"/>
                </div>
                <div className="tooltip" 
                data-tip={getObservationFilesString()}>
                <DocumentChartBarIcon id="ObservationFilesIcon" className="size-8"/>
                </div>
                <div className="tooltip" 
                data-tip={getLogSheetFilesString()}>
                <DocumentMagnifyingGlassIcon id="LogSheetIcon" className="size-8"/>
                </div>
                <div className="tooltip" 
                data-tip={getOtherFilesString()}> 
                <DocumentIcon id="OtherFilesIcon" className="size-8"/>
                </div>
            </div>
            {loadingVisitImages ? (
                <div className="w-full h-60 flex rounded-md flex-col items-center justify-center ">
                <span className="text-xl font-semibold mb-12">
                    Loading images
                </span>
                <Spinner size="lg" />
                </div>
            ) : (
                <div
                className={`grid grid-cols-2 gap-3 items-start place-items-center overflow-auto`}
                >
                <>
                    {visitImages?.map(
                    (img) => {
                        return (
                        <img
                            key={
                            img.id
                            }
                            src={
                            "data:image/png;base64," +
                            img.actual_image
                            }
                            alt={
                            img.description
                            }
                            className="shadow-xl rounded-lg object-center object-contain w-full h-full"
                        />
                        );
                    },
                    )}
                </>
                </div>
            )}
            {visit.navigation_filename && (
                <div className="w-full h-60 overflow-hidden rounded-lg">
                <MapVisit
                    base64Data={
                    visit.navigation_actual_file ??
                    ""
                    }
                    station={station}
                    statuses = {statuses}
                    types = {types}
                />
                </div>
            )}
            </div>
        </div>
    );
};

export default VisitThumbNail;
