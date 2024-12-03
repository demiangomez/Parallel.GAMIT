import { CampaignsTable } from "@componentsReact";

const Campaigns = () => {
    return (
        <div className="p-4 space-y-12">
            <div className="w-full text-center mt-4">
                <span className="text-4xl font-bold"> Campaigns </span>
            </div>
            <div className="flex w-full justify-center">
                <CampaignsTable />
            </div>
        </div>
    );
};

export default Campaigns;
