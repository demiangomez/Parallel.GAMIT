import { Modal, VisitsCampaingTable } from '@components/index';
import {StationVisitsData, CampaignsData} from '@types';
import { useEffect, useState } from 'react';

interface VisitsCampaignModalProps {
    visits: StationVisitsData[] 
    campaign: CampaignsData | undefined
    setCampaign: React.Dispatch<React.SetStateAction<CampaignsData | undefined>>
}

const VisitsCampaignModal = ({visits, campaign, setCampaign}:VisitsCampaignModalProps) => {
    
    const titles = ["date","edit", "station", "people", "other_file_count", "observation_file_count", "log_sheet_filename", "comments", "visit_image_count"]

    const [orderedVisits, setOrderedVisits] = useState<StationVisitsData[]>([])

    useEffect(() => {
        if(visits){
            const ordered = visits.sort((a,b) => {
                if(a.date > b.date) return -1
                if(a.date < b.date) return 1
                return 0
            })
            setOrderedVisits(ordered)
        }
    },[visits])    


    return (  
        <Modal size='fit' close={false} modalId="Visits" handleCloseModal={() => {setCampaign(undefined)}}>
            <div className="w-full flex flex-col justify-start items-center">
                <h3 className="font-bold text-center text-2xl my-2 w-full">
                    {campaign?.name.toUpperCase()} 
                </h3>
                <div className="space-y-4 max-h-[70vh] overflow-y-auto p-4">
                    <VisitsCampaingTable visits={orderedVisits} campsToShow={titles}/>
                </div>
            </div>
        </Modal>
    );
}
 
export default VisitsCampaignModal;