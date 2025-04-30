import { useEffect, useMemo, useState } from "react";

import {
    StationPeopleModal,
    Pagination,
    Table,
    TableCard,
} from "@componentsReact";

import { useAuth, useApi } from "@hooks";

import { showModal } from "@utils";

import { getPeopleService } from "@services";

import { GetParams, People, PeopleServiceData } from "@types";
import MergePeopleModal from "@components/modals/MergePeopleModal";

const PeopleTable = () => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const bParams: GetParams = useMemo(() => {
        return {
            limit: 5,
            offset: 0,
        };
    }, []);

    const [modals, setModals] = useState<
        | { show: boolean; title: string; type: "add" | "edit" | "none" }
        | undefined
    >(undefined);

    const [loading, setLoading] = useState<boolean>(true);
    const [params, setParams] = useState<GetParams>(bParams);

    const [allPeople, setAllPeople] = useState<People[]>([]);
    const [peoples, setPeoples] = useState<People[]>([]);
    const [people, setPeople] = useState<People | undefined>(undefined);

    const [activePage, setActivePage] = useState<number>(1);
    const [pages, setPages] = useState<number>(0);
    const PAGES_TO_SHOW = 2;
    const REGISTERS_PER_PAGE = 5; // Es el mismo que params.limit

    const getPeople = async () => {
        try {
            setLoading(true);
            const res = await getPeopleService<PeopleServiceData>(api, params);
            setPeoples(res.data);
            if (bParams.limit) {
                setPages(Math.ceil(res.total_count / bParams.limit));
            }
            res.data && res.data.length === 0 && handlePage(1);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const getAllPeople = async () => {
        try {
            setLoading(true);
            const res = await getPeopleService<PeopleServiceData>(api);
            setAllPeople(res.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const paginatePeople = async (newParams: GetParams) => {
        try {
            setLoading(true);
            const res = await getPeopleService<PeopleServiceData>(
                api,
                newParams,
            );
            setPeoples(res.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handlePage = (page: number) => {
        if (page < 1 || page > pages) return;
        let newParams;
        if (page === 1) {
            newParams = {
                ...params,
                limit: REGISTERS_PER_PAGE * 1,
                offset: REGISTERS_PER_PAGE * (page - 1),
            };
        } else {
            newParams = {
                ...params,
                limit: REGISTERS_PER_PAGE,
                offset: REGISTERS_PER_PAGE * (page - 1),
            };
        }

        setParams(newParams);
        setActivePage(page);
        paginatePeople(newParams);
    };

    const reFetch = () => {
        getPeople();
    };

    useEffect(() => {
        getPeople();
        getAllPeople();
    }, []); // eslint-disable-line

    const titles = [
        "Username",
        "Name",
        "Lastname",
        "Email",
        "Phone",
        "Address",
        "Institution",
        "Position",
    ];

    const body = useMemo(() => {
        return peoples
            ?.sort((a, b) => a.last_name.localeCompare(b.last_name))
            .map((st) =>
                Object.values({
                    username: st.user_name,
                    name: st.first_name,
                    lastname: st.last_name,
                    email: st.email,
                    phone: st.phone,
                    address: st.address,
                    institution: st.institution,
                    position: st.position,
                }),
            );
    }, [peoples]);

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);

    return (
        <TableCard
            title={"Station People"}
            size={"650px"}
            addButtonTitle="+ Person"
            modalTitle="EditPerson"
            setModals={setModals}
            addButton={true}
            secondAddButton={true}
            secondAddButtonTitle="Merge"
            secondModalTitle="MergePeople"
        >
            <Table
                titles={body && body.length > 0 ? titles : []}
                body={body}
                table={"people"}
                loading={loading}
                dataOnly={false}
                onClickFunction={() =>
                    setModals({
                        show: true,
                        title: "EditPerson",
                        type: "edit",
                    })
                }
                setState={setPeople}
                state={peoples}
            />
            {body && body.length > 0 ? (
                <Pagination
                    pages={pages}
                    pagesToShow={PAGES_TO_SHOW}
                    activePage={activePage}
                    handlePage={handlePage}
                />
            ) : null}
            {modals?.show && modals.title === "EditPerson" && (
                <StationPeopleModal
                    Person={people}
                    modalType={modals.type}
                    setStateModal={setModals}
                    setPerson={setPeople}
                    reFetch={reFetch}
                />
            )}
            {modals?.show &&
                modals.title === "MergePeople" &&
                body &&
                body.length > 0 && (
                    <MergePeopleModal
                        setStateModal={setModals}
                        handleCloseModal={() => setModals(undefined)}
                        body={allPeople as People[]}
                    />
                )}
        </TableCard>
    );
};

export default PeopleTable;
