import { useEffect, useState } from "react";

import {
    SourcesServersPage,
    SourcesFormatsPage,
    CardContainer,
} from "@componentsReact";

import { getSourcesFormatsService, getSourcesServersService } from "@services";

import { useAuth, useApi, useResize } from "@hooks";

import { showModal } from "@utils";

import {
    SourcesFormatData,
    SourcesFormatServiceData,
    SourcesServerData,
    SourcesServerServiceData,
} from "@types";

const SourcesPage = () => {
    const { token, logout } = useAuth();

    const height = useResize();

    const [modals, setModals] = useState<
        | {
              show: boolean;
              title: string;
              type: "add" | "edit" | "none";
          }
        | undefined
    >(undefined);

    const [loading, setLoading] = useState<boolean>(true);

    const [sourcesServers, setSourcesServers] = useState<
        SourcesServerData[] | undefined
    >(undefined);

    const [sourcesFormats, setSourcesFormats] = useState<
        SourcesFormatData[] | undefined
    >(undefined);

    const api = useApi(token, logout);

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

    const refetch = () => {
        Promise.all([
            setLoading(true),
            getSourcesServers(),
            getSourcesFormats(),
        ]).then(() => {
            setLoading(false);
        });
    };

    useEffect(() => {
        refetch();
    }, []);

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    return (
        <div className="p-4 flex flex-col justify-center items-center w-full h-full">
            <>
                <div className="w-full text-center mt-6">
                    <span className="text-4xl font-bold">Sources</span>
                </div>
                <div className="flex flex-grow w-full justify-center">
                    <div
                        className={`flex lg flex-col min-w-[80%] 
                            justify-center items-center gap-2 overflow-y-auto`}
                    >
                        <>
                            <CardContainer
                                title={""}
                                height={height}
                                addButton={false}
                            >
                                <SourcesServersPage
                                    loading={loading}
                                    sourcesFormats={sourcesFormats}
                                    modals={modals}
                                    setModals={setModals}
                                    sourcesServers={sourcesServers}
                                    api={api}
                                    refetch={refetch}
                                />
                            </CardContainer>
                            <CardContainer
                                title={""}
                                height={false}
                                addButton={false}
                            >
                                <SourcesFormatsPage
                                    setModals={setModals}
                                    sourcesFormats={sourcesFormats}
                                    api={api}
                                    loading={loading}
                                    modals={modals}
                                    refetch={refetch}
                                />
                            </CardContainer>
                        </>
                    </div>
                </div>
            </>
        </div>
    );
};

export default SourcesPage;
