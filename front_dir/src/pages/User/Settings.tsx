//Utils
import { PeopleSettingsForm, UserSettingsForm } from "@componentsReact";
import { useAuth } from "@hooks";

const Settings = () => {
    //Exportar user del usecontext
    const { user } = useAuth();

    return (
        <div className="justify-items-center">
            <h3 className="text-3xl font-bold mt-4">Settings</h3>
            {user ? (
                <div
                    className={`w-full gap-4 p-6 flex  ${user?.person === null ? "flex-row " : "lg:flex-col "} `}
                >
                    <div className="flex-1 min-w-0">
                        <UserSettingsForm userData={user} />
                    </div>
                    <div className="flex-1 min-w-0">
                        {user.person ? (
                            <PeopleSettingsForm person={user.person} />
                        ) : (
                            <div className=" w-full text-center text-neutral text-2xl font-bold rounded-md bg-neutral-content p-6">
                                This user does not have an assigned person
                            </div>
                        )}
                    </div>
                </div>
            ) : (
                <div className="w-full flex justify-center items-center p-10">
                    <div className="loading loading-spinner loading-lg"></div>
                </div>
            )}
        </div>
    );
};

export default Settings;
