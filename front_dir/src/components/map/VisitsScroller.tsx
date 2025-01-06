import { Scroller } from "@componentsReact";

import { StationVisitsData, StationMetadataServiceData } from "@types";
import { useEffect } from "react";

interface VisitsScrollerProps {
    map?: L.Map | null;
    visits: StationVisitsData[];
    changeKml: VisitsStates[];
    changeMeta: boolean;
    setChangeKml: React.Dispatch<React.SetStateAction<VisitsStates[]>>;
    setChangeMeta: React.Dispatch<React.SetStateAction<boolean>>;
    stationMeta: StationMetadataServiceData;
    showScroller: boolean;
    setShowScroller: React.Dispatch<React.SetStateAction<boolean>>;
}

interface VisitsStates {
    visitId: number;
    checked: boolean;
}

const VisitsScroller = ({
    map,
    visits,
    changeKml,
    changeMeta,
    setChangeKml,
    setChangeMeta,
    stationMeta,
    showScroller,
    setShowScroller,
}: VisitsScrollerProps) => {

    useEffect(() => {
        if(changeKml.length === 0)
        {
            if(visits)
            {
                const newChangeKml: VisitsStates[] = [];

                visits?.forEach((visit) => {
                    const newKml = {visitId: visit.id, checked: false};
                    
                    newChangeKml.push(newKml);
                });
            
                setChangeKml(newChangeKml);
            }

            
        }   

        

    }, [showScroller]);

   

    return (
        <>
            <Scroller
                map={map}
                buttonCondition={
                    (Array.isArray(visits) && visits.length > 0) ||
                    !!stationMeta?.navigation_actual_file
                }
                scrollerCondition={visits && showScroller}
                scrollerName="Show routes"
                showScroller={showScroller}
                setShowScroller={setShowScroller}
                fromMain={false}
            >
                <div className="form-control">
                    <label className="label cursor-pointer truncate">
                        <span className="font-bold mr-4">Select All</span>
                        <input
                            type="checkbox"
                            className="checkbox checkbox-sm"
                            checked={
                                changeKml.length > 0 &&
                                changeKml.every(
                                    (visitBool) => visitBool.checked,
                                ) &&
                                changeMeta
                            }
                            onChange={(e) => {
                                if (changeKml.length !== 0) {
                                    setChangeMeta(e.target.checked);
                                    setChangeKml((prev) => {
                                        return prev.map((visitBool) => ({
                                            ...visitBool,
                                            checked: e.target.checked,
                                        }));
                                    });
                                } else if (changeKml.length === 0) {
                                    setChangeMeta(e.target.checked);
                                    if (e.target.checked) {
                                        setChangeKml(
                                            visits.map((visit) => ({
                                                visitId: visit.id,
                                                checked: true,
                                            })),
                                        );
                                    } else {
                                        setChangeKml(
                                            visits.map((visit) => ({
                                                visitId: visit.id,
                                                checked: false,
                                            })),
                                        );
                                    }
                                }
                            }}
                        />
                    </label>
                </div>
                {stationMeta?.navigation_actual_file && (
                    <div className="form-control">
                        <label className="label cursor-pointer">
                            <span className="font-bold mr-4">Default</span>
                            <input
                                type="checkbox"
                                className="checkbox checkbox-sm"
                                checked={changeMeta}
                                onChange={(e) => {
                                    setChangeMeta(e.target.checked);
                                }}
                            />
                        </label>
                    </div>
                )}
                {visits.map((visit) => (
                    <div className="form-control" key={visit.id}>
                        <label className="label cursor-pointer">
                            <span
                                className="font-bold mr-2 truncate"
                                title={
                                    visit.campaign_name && visit.date
                                        ? visit.campaign_name +
                                          " - " +
                                          visit.date
                                        : visit.date
                                }
                            >
                                {visit.date && "Visit - " + visit.date}
                            </span>
                            <input
                                type="checkbox"
                                className="checkbox checkbox-sm"
                                checked={changeKml.some(
                                    (visitBool) =>
                                        visitBool.visitId === visit.id &&
                                        visitBool.checked,
                                )}
                                onChange={(e) => {
                                    setChangeKml((prev) => {
                                        const visitToMod = prev.find(
                                            (visitBool) =>
                                                visitBool.visitId === visit.id,
                                        );
                                        if (visitToMod) {
                                            return prev.map((visitBool) =>
                                                visitBool.visitId === visit.id
                                                    ? {
                                                          ...visitBool,
                                                          checked:
                                                              e.target.checked,
                                                      }
                                                    : visitBool,
                                            );
                                        } else {
                                            return [
                                                ...prev,
                                                {
                                                    visitId: visit.id,
                                                    checked: e.target.checked,
                                                },
                                            ];
                                        }
                                    });
                                }}
                            />
                        </label>
                    </div>
                ))}
            </Scroller>
        </>
    );
};

export default VisitsScroller;
