import { StationVisitsData } from '@types';
import { Link } from 'react-router-dom';
import React from 'react';

interface VisitsCampaignTableProps {
    visits: StationVisitsData[] 
    campsToShow: string[]
}
const VisitsCampaignTable = ({visits, campsToShow}:VisitsCampaignTableProps) => {    

    const [groupedVisits, setGroupedVisits] = React.useState<{date: string, visits:StationVisitsData[]}[] | undefined>(undefined);

    const groupVisits = () => {
        const grouped: {date: string, visits:StationVisitsData[]}[] = [];
        if(visits){
            for(let i = 0; i < visits.length; i++){
                const auxiliarGroup = {date: "1/1/1", visits:[] as StationVisitsData[]};
                const currentVisitDate = new Date(visits[i].date).toLocaleDateString('es-ES', {
                    month: 'numeric',
                    day: 'numeric',
                    year: 'numeric'
                });
                if(grouped.length === 0){
                    auxiliarGroup.visits.push(visits[i])
                    auxiliarGroup.date = currentVisitDate;
                    grouped.push(auxiliarGroup);
                }
                else{
                    const filter = grouped.find((group) => {
                        const filteredVisit = group.visits.filter(() =>{
                            const groupVisitDate = group.date
                            return groupVisitDate === currentVisitDate
                        })
                        return filteredVisit.length > 0;
                    })
                    if(filter){
                        const index = grouped.indexOf(filter);
                        grouped[index].visits.push(visits[i]);
                    }
                    else{
                        auxiliarGroup.visits.push(visits[i])
                        auxiliarGroup.date = currentVisitDate;
                        grouped.push(auxiliarGroup);
                    }
                }
            setGroupedVisits(grouped);
            }
        }
    }

    React.useEffect(() => {
        groupVisits();
    }, [visits]);

    const getPeopleString = (visit: StationVisitsData) => {
        let peopleString = "-"
        if(visit.people !== undefined){
            if(visit.people.length > 0){
                const peopleNames = visit.people.map((person: {id: number, name: string}) => person.name);
                peopleString = peopleNames.join(', ')
            }
        }
        return peopleString
    }

    const getStationCode = (visit: StationVisitsData) => {
        return (visit.station_formatted)?.split('.')[1]

    }

    const getStationNetwork = (visit: StationVisitsData) => {
        return (visit.station_formatted)?.split('.')[0]
    }



    return (  
        <div className="max-h-[500px] overflow-auto">
            <table className='table bg-neutral-content'>
                <thead>
                    <tr className=''>
                    {
                        campsToShow.map((camp, index) => (
                            <th className="text-neutral text-center" key={index}>{camp.replace(/_/g, ' ').toUpperCase()}</th>
                        ))
                    }
                    </tr>
                </thead>
                <tbody className="bg-base-200">
                    {
                        groupedVisits?.map((groupedVisit) => (
                            <>
                                <tr className=''>
                                    <td rowSpan={groupedVisit.visits.length + 1} className="border-b-2 border-t-2 border-solid border-neutral-400 text-center bg-base-300 align-middle">
                                        {groupedVisit.date}
                                    </td>
                                </tr>
                                {groupedVisit.visits.map((visit) => (
                                    <tr key={`${visit.date}_${visit.station_formatted}`} className='border-2 border-solid border-neutral-400'>
                                    {
                                        campsToShow.map((camp, index2) => (
                                            camp === "people" ? (
                                                <td key={index2} className="text-center align-middle border-y-2 border-solid border-neutral-400">
                                                    <div className="max-w-[200px] max-h-[40px] overflow-y-auto overflow-x-auto">
                                                        {getPeopleString(visit)}
                                                    </div>
                                                </td>
                                            ) : camp === "edit" ? (
                                                <td key={index2} className='text-center align-middle border-y-2 border-solid border-neutral-400'>
                                                    <Link 
                                                        to={`/${getStationNetwork(visit)}/${getStationCode(visit)}/visits`}
                                                        state={{
                                                            visitDetail: visit,
                                                        }}
                                                    >
                                                        📝
                                                    </Link>
                                                </td>
                                            ) : camp === "comments" && visit[camp] !== "" ? (
                                                <td key={index2} className="text-center align-middle border-y-2 border-solid border-neutral-400">
                                                    <div className="max-w-[200px] max-h-[40px] overflow-y-auto overflow-x-hidden break-words">
                                                        <div dangerouslySetInnerHTML={{
                                                            __html: visit[camp] ?? "",
                                                        }} />
                                                    </div>
                                                </td>
                                            ) : camp === "station" ? (
                                                <td key={index2} className="text-center align-middle border-y-2 border-solid border-neutral-400">
                                                    {visit.station_formatted !== "" ? visit.station_formatted : "-"}
                                                </td>
                                            ) : camp !== "date" ? (
                                                <td key={index2} className="text-center align-middle border-y-2 border-solid border-neutral-400">
                                                    {visit[camp] !== "" ? visit[camp] : "-"}
                                                </td>
                                            ) : null
                                        ))
                                    }
                                    </tr>
                                ))}
                            </>
                        ))
                    }
                </tbody>
            </table>
        </div>
    );
}
 
export default VisitsCampaignTable;