import {
    StationData,
    SourcesServerData,
    SourcesServerServiceData,
    SourcesFormatServiceData,
    SourcesFormatData,
    SourcesStationsData,
    SourcesStationsServiceData,
} from "@types";
import { useOutletContext } from "react-router-dom";
import {
    getSourcesServersService,
    getSourcesFormatsService,
    getSourcesStationsByStationIdService,
} from "@services";
import {
    CardContainer,
    StationChangeTryOrderModal,
    StationSourcesModal,
    Table,
    TableCard,
} from "@componentsReact";
import { showModal } from "@utils";
import { useAuth, useApi } from "@hooks";
import { useEffect, useMemo, useState } from "react";
interface OutletContext {
    station: StationData;
}

const Sources = () => {
    const { station } = useOutletContext<OutletContext>();

    const { token, logout } = useAuth();

    const api = useApi(token, logout);

    const [modals, setModals] = useState<
        | {
              show: boolean;
              title: string;
              type: "add" | "edit" | "none";
          }
        | undefined
    >(undefined);

    const [loading, setLoading] = useState<boolean>(false);

    const [sourcesServers, setSourcesServers] = useState<
        SourcesServerData[] | undefined
    >(undefined);

    const [sourcesFormats, setSourcesFormats] = useState<
        SourcesFormatData[] | undefined
    >(undefined);

    const [sourcesStations, setSourcesStations] = useState<
        SourcesStationsData[]
    >([]);

    const [data, setData] = useState<string[][]>([]);

    const [sourceStation, setSourceStation] = useState<
        SourcesStationsData | undefined
    >(undefined);

    const titles =
        sourcesStations.length > 0
            ? ["try_order", "path", "server", "format"]
            : [];

    const getSourcesServers = async () => {
        try {
            const res =
                await getSourcesServersService<SourcesServerServiceData>(api);
            if (res.statusCode === 200 && res.data) {
                setSourcesServers(res.data);
            }
        } catch (error) {
            console.error(error);
        }
    };

    const getSourcesFormats = async () => {
        try {
            const res =
                await getSourcesFormatsService<SourcesFormatServiceData>(api);
            if (res.statusCode === 200 && res.data) {
                setSourcesFormats(res.data);
            }
        } catch (error) {
            console.error(error);
        }
    };

    const getSourcesStations = async () => {
        try {
            const res =
                await getSourcesStationsByStationIdService<SourcesStationsServiceData>(
                    api,
                    station.network_code,
                    station.station_code,
                );
            if (res.statusCode === 200 && res.data) {
                const orderedSourcesStations = res.data.sort(
                    (a, b) => a.try_order - b.try_order,
                );
                setSourcesStations(orderedSourcesStations);
            }
        } catch (error) {
            console.error(error);
        }
    };

    const handleCloseModal = () => {
        setModals(undefined);
        setSourceStation(undefined);
    };

    const handleEdit = () => {
        setModals({
            show: true,
            title: "Station Sources",
            type: "edit",
        });
    };

    const refetch = () => {
        Promise.all([
            setLoading(true),
            getSourcesServers(),
            getSourcesStations(),
            getSourcesFormats(),
        ]).then(() => {
            setLoading(false);
        });
    };

    useMemo(() => {
        if (sourcesStations && sourcesServers && sourcesFormats) {
            const newData: string[][] = [];
            sourcesStations.forEach((sourceStation) => {
                const server = sourcesServers.find(
                    (server) => server.server_id === sourceStation.server_id,
                );
                const serverData = server
                    ? server.fqdn + " " + server.protocol
                    : "N/A";
                const format = sourceStation.format;
                const path =
                    typeof sourceStation.path === "string"
                        ? sourceStation.path
                        : "N/A";
                const auxNewData = [
                    sourceStation.try_order.toString(),
                    path,
                    serverData,
                    format,
                ];
                newData.push(auxNewData);
            });
            setData(newData);
        }
    }, [sourcesStations, sourcesServers, sourcesFormats]);

    useEffect(() => {
        refetch();
    }, []);

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    return (
        <div className="">
            <h1 className="text-2xl font-base text-center">RINEX SOURCES</h1>
            <div className="flex flex-grow w-full justify-center pr-2 space-x-2 px-8 pb-4">
                <CardContainer title={""} height={false} addButton={false}>
                    <TableCard
                        title={"Sources"}
                        size={"100%"}
                        addButtonTitle="+ Source Station"
                        setModals={setModals}
                        addButton={true}
                        modalTitle="Station Sources"
                        secondAddButton={true}
                        secondAddButtonTitle="Change Try Order"
                        secondModalTitle="Change Try Order"
                    >
                        <Table
                            table="sources"
                            titles={titles ?? []}
                            body={data.length > 0 ? data : undefined}
                            loading={loading}
                            onClickFunction={handleEdit}
                            deleteRegister={false}
                            state={sourcesStations}
                            setState={setSourceStation}
                        />
                    </TableCard>
                </CardContainer>
            </div>
            {modals?.show && modals.title === "Station Sources" && (
                <StationSourcesModal
                    api={api}
                    sourcesServers={sourcesServers}
                    sourcesFormats={sourcesFormats}
                    sourceStation={sourceStation}
                    type={modals.type}
                    handleClose={handleCloseModal}
                    station={station}
                    refetch={refetch}
                />
            )}
            {modals?.show && modals.title === "Change Try Order" && (
                <StationChangeTryOrderModal
                    api={api}
                    sourcesServers={sourcesServers}
                    sourcesStations={sourcesStations}
                    handleCloseModal={() => {
                        setModals(undefined);
                        setSourceStation(undefined);
                    }}
                    refetch={refetch}
                />
            )}
        </div>
    );
};

export default Sources;
