import { EarthquakeData } from "@types";

interface EarthQuakePopupChildrenProps{
    earthQuake: EarthquakeData;
}

const EarthQuakePopupChildren = ({ earthQuake }: EarthQuakePopupChildrenProps) => {
    return (
        <>        
            <div
                className={`flex flex-col self-start space-y-2 max-h-82 overflow-y-auto pr-2 md:w-[400px] lg:w-[450px] `}
            >
                <span className="w-full bg-green-400 px-4 py-1 text-center font-bold self-center">
                    {"Earthquake id: " + earthQuake.api_id}
                </span>
            </div>
        </>
    );
}
 
export default EarthQuakePopupChildren;