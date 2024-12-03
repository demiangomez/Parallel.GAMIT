import { RolesTable, UsersTable } from "@componentsReact";
import "@assets/child.css";

const Users = () => {
    return (
        <div className="my-auto">
            <div className="w-full text-center">
                <span className="text-4xl font-bold"> Users </span>
            </div>
            <div
                className="flex flex-wrap xl:space-x-2 xl:mt-4 
            xl:flex-col xl:items-center xl:space-y-4 custom-padding margin-custom
            justify-center transition-all duration-200 py-4"
            >
                <UsersTable />
                <RolesTable />
            </div>
        </div>
    );
};

export default Users;
