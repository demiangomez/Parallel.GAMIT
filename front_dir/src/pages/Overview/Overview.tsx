import {
    MonumentsTable,
    StationStatusTable,
    StationRolesTable,
    PeopleTable,
    StationTypesTable,
} from "@componentsReact";

const Overview = () => {
    return (
        <div className="p-4 ">
            <div className="w-full text-center mt-6">
                <span className="text-4xl font-bold"> Overview </span>
            </div>
            <div className="w-full grid grid-cols-2 grid-flow-dense gap-4 my-6 xl:grid-cols-1">
                <div className="flex flex-col space-y-4 items-end xl:items-center ">
                    <MonumentsTable />
                    <StationStatusTable />
                </div>
                <div className="flex flex-col items-start space-y-4 xl:items-center">
                    <PeopleTable />
                    <StationRolesTable />
                    <StationTypesTable />
                </div>
            </div>
        </div>
    );
};

export default Overview;
