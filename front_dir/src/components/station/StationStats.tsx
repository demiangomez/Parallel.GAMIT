import { useOutletContext } from "react-router-dom";
import { CardContainer } from "@componentsReact";

import { StationData } from "@types";

const StationStats = () => {
    const station: StationData = useOutletContext(); // eslint-disable-line

    // TENGO LA ESTACION DEL OUTLET
    // TODO: AGREGAR LAS STATS DEL pyEMT.py

    return (
        <div className="">
            <h1 className="text-2xl font-base text-center">STATS</h1>
            <div className="flex w-full justify-center pr-2 space-x-2 px-2">
                <CardContainer title="Charts" titlePosition="start">
                    <div>Not implemented yet ..</div>
                </CardContainer>
            </div>
        </div>
    );
};

export default StationStats;
