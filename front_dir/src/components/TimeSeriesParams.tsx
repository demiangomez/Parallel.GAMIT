import { TimeSeriesConfigModal, ConfirmDeleteModal} from "components"
import { resetTimeSeriesPeriodicService, resetTimeSeriesJumpsService, resetTimeSeriesPolynomialService
    , postTimeSeriesPeriodicService, postTimeSeriesJumpService, deleteTimeSeriesJumpService, getJumpTypesService
 } from "@services";
import { useAuth, useApi } from "@hooks";
import  { useEffect, useState } from 'react';
import {  ConfigJumpData, ConfigPolynomialData, Errors, JumpType} from "@types";
import { PencilSquareIcon, XMarkIcon, ArrowPathIcon, PlusIcon, MinusIcon } from "@heroicons/react/24/outline";
import { showModal, apiOkStatuses } from "@utils";


interface TimeSeriesParamsProps {
    stationId: number;
    solution: string;
    refetch: () => void;
    jumpsData: ConfigJumpData[] | undefined;
    periodicData: any | undefined;
    polynomialData: ConfigPolynomialData | undefined;
    stack : string
}

const TimeSeriesParams = ({stationId, refetch, solution, jumpsData, periodicData, polynomialData, stack}: TimeSeriesParamsProps) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);

    const [loadingConfirmModal, setLoadingConfirmModal] = useState(false);

    const [msg, setMsg] = useState<
                { status: number; msg: string; errors?: Errors } | undefined
        >(undefined);

    const [success, setSuccess] = useState(false);

    

    const [modals, setModals] = useState<
            | { show: boolean; title: string; type: "add" | "edit" | "none" }
            | undefined
        >(undefined);

    const [data, setData] = useState<any>(undefined);

    const [jumpTypes, setJumpTypes] = useState<JumpType[]>([]);
    const [modalType, setModalType] = useState<{table: string, type: string} | undefined>(undefined);
    const [valueToModify, setValueToModify] = useState<any | undefined>(undefined);

    const formatDate = (year: number, doy: number) => {
        const date = new Date(year, 0, doy).toISOString().split('T')[0];
        const doyFormatted = doy.toString().padStart(3, '0');
        const finalDate = date + " (" + year + " " + doyFormatted + ")"
        return finalDate
    };

    const getRelaxation= (relaxations: number[]) => {
        const finalRelaxation = relaxations.join(", ");
        return finalRelaxation
    }
    
    const resetData = async () =>{
        try{
            setLoadingConfirmModal(true);
            const service = modalType?.table === "polynomial" ? resetTimeSeriesPolynomialService : modalType?.table === "periodic" ? resetTimeSeriesPeriodicService : resetTimeSeriesJumpsService;
            const res = await service<any>(api, stationId, solution, stack);
            if ("status" in res) {
                setMsg({
                    status: res.statusCode,
                    msg: res.response.type,
                    errors: res.response,
                });
            } else {
                setMsg({
                    status: res.statusCode,
                    msg: "Row has been reset successfully",
                });
            }
        }
        catch(e){
            console.error(e);
        }
        finally{
            setLoadingConfirmModal(false);
        }
    }


    const deactivateRow = async () => {
        if(valueToModify){
            if(modalType?.table === "jumps"){
                const type = valueToModify.type < 10 ? 0 : valueToModify.type >= 10 ? 1 : 2;
                const params = {
                    Year: valueToModify.Year,
                    DOY: valueToModify.DOY,
                    action: "-",
                    jump_type :  type,
                }
                try{
                    setLoadingConfirmModal(true);
                    const res = await postTimeSeriesJumpService<any>(api, stationId, solution, stack, params);
                    if ("status" in res) {
                        setMsg({
                            status: res.statusCode,
                            msg: res.response.type,
                            errors: res.response,
                        });
                    } else {
                        setMsg({
                            status: res.statusCode,
                            msg: "Row has been deactivated successfully",
                        });
                    }
                }
                catch(e){
                    console.error(e);
                }
                finally{
                    setLoadingConfirmModal(false);
                }
            }
        }
    }

    const getJumpTypes = async () =>{
        try{
            const res = await getJumpTypesService<{jump_types: JumpType[]}>(api);
            setJumpTypes(res.jump_types);
        }
        catch(e){
            console.error(e);
        }
    }

    const chosenRowColor = (action: string) => {
        if(action === "-"){
            return "bg-gray-200"
        }
        if(action === "+"){
            return "bg-green-200"
        }
        if(action === "A"){
            return "bg-green-400"
        }
        return
    }


    const deleteRow = async () => {
        if(valueToModify){
            if(modalType?.table === "jumps"){
                const params = {
                    Year: valueToModify.Year,
                    DOY: valueToModify.DOY,
                }
                try{
                    setLoadingConfirmModal(true);        
                    const res = await deleteTimeSeriesJumpService<any>(api, stationId, solution ,params);
                    if ("status" in res) {
                        setMsg({
                            status: res.statusCode,
                            msg: res.response.type,
                            errors: res.response,
                        });
                    } else {
                        setMsg({
                            status: res.statusCode,
                            msg: "Row has been deleted successfully",
                        });
                    }
                }
                catch(e){
                    console.error(e);
                }
                finally{
                    setLoadingConfirmModal(false);
                }
            }
            if(modalType?.table === "periodic"){
                const valueKey = Object.keys(valueToModify)[0];
                const newPeriodicData = Object.keys(periodicData).filter((key) => key !== valueKey);
                const params = {frequencies: newPeriodicData.map(key => Number(key))};
                try{
                    setLoadingConfirmModal(true);
                    const res = await postTimeSeriesPeriodicService<any>(api, stationId, solution , stack, params);
                    if ("status" in res) {
                        setMsg({
                            status: res.statusCode,
                            msg: res.response.type,
                            errors: res.response,
                        });
                    } else {
                        setMsg({
                            status: res.statusCode,
                            msg: "Row has been deleted successfully",
                        });
                    }
                }
                catch(e){
                    console.error(e);
                }
                finally{
                    setLoadingConfirmModal(false);
                }
            }
        }
    }
    
    useEffect(() => {
        getJumpTypes();
    },[])

    useEffect(() => {
        if(modalType){
            if(modalType.type === "add"){
                setModals({ show: true, title: "TimeSeriesConfigModal", type: "add" });
            }
            if(modalType.type === "activate"){
                setModals({ show: true, title: "TimeSeriesConfigModal", type: "none" });
            }
            if(modalType.type === "edit"){
                setModals({ show: true, title: "TimeSeriesConfigModal", type: "edit" });
            }
            if(modalType.type === "delete"){
                setModals({ show: true, title: "ConfirmDelete", type: "none" });
            }
            if(modalType.type === "reset"){
                setModals({ show: true, title: "ConfirmDelete", type: "none" });
            }
            if(modalType.type === "deactivate"){
                setModals({ show: true, title: "ConfirmDelete", type: "none" });
            }
            
        }
    }, [modalType]);

    useEffect(() => {
        modals?.show && showModal(modals.title);
    }, [modals]);



    return (
    
    <div className="p-4 space-y-8 flex flex-col bg-white">
        { polynomialData !== undefined ?
        <div className="w-full flex flex-row justify-between items-start gap-4">
            <div className="flex flex-col justify-center items-center bg-gray-200 w-[40%] pb-2 pt-2">
            <div className="bg-gray-200 pb-2">
                <label htmlFor="" className="font-bold">Polynomial terms</label>
            </div>
            
            <div>
                <label htmlFor="" className="font-bold">Conventional epoch</label>
            </div>
            </div>
            <div className="flex flex-col justify-center items-center w-[40%] pb-2 pt-2 bg-gray-100">
            <div className=" text-center w-full pb-2">
                {polynomialData?.terms}
            </div>
            <div className=" text-center">
                <label htmlFor="">
                {polynomialData?.Year}
                </label>
            </div>
            </div>
            <div className="flex flex-col justify-center items-center w-[40%] pb-2 pt-2 bg-gray-100">
            <div className=" text-center pb-2 flex flex-row justify-center items-center gap-3">
                <PencilSquareIcon className="size-6 hover:text-black cursor-pointer"
                    onClick={() => {
                        setModalType({table: "polynomial", type: "edit"})
                        setValueToModify(polynomialData);
                    }}
                /> 
                <ArrowPathIcon 
                    className="size-6 hover:text-black cursor-pointer"
                    onClick={() => {
                        setModalType({table: "polynomial", type: "reset"})
                        setValueToModify(polynomialData)
                    }}
                />
            </div>
            <div className=" text-center">
                <label htmlFor="">
                {polynomialData?.DOY}
                </label>
            </div>
            </div>
        </div>
        :
        <div className="w-full bg-gray-200 p-4 flex justify-center items-center">
            <h2 className="font-bold text-lg">The polynomial table is disabled</h2>
        </div>
        }
        <div>
            <div className="overflow-x-auto">
            <table className="min-w-full border border-gray-300">
            <thead>
            <tr className="bg-gray-200">
                <th className="p-3 text-center border border-gray-300" colSpan={2}>Periodic components</th>
                <th className="p-3 text-center border border-gray-300">
                <div className="flex flex-row justify-center items-center gap-4">
                    <PlusIcon 
                        className="size-6 hover:text-green-600 cursor-pointer" 
                        onClick={() => {setModalType({table: "periodic", type: "add"})
                        setData(Object.keys(periodicData).map((key) => parseFloat(key)))
                        }}
                    />
                    <ArrowPathIcon 
                        className="size-6 hover:text-black cursor-pointer"
                        onClick={() => {setModalType({table: "periodic", type: "reset"})}}
                    />
                </div>    
                </th>
            </tr>
            <tr>
                <th className="p-3 text-center border border-gray-300 w-16">Edit</th>
                <th className="p-3 text-center border border-gray-300">Values</th>
                <th className="p-3 text-center border border-gray-300">State</th>
            </tr>
            </thead>
            <tbody>
            {periodicData && 
                Object.entries(periodicData).map(([key, value]) => (
                    <tr key={key}>
                        <td className="p-3 text-center border border-gray-300">
                            <div className="flex justify-center items-center h-full">
                                <XMarkIcon className="size-6 hover:text-red-500 cursor-pointer"
                                    onClick={() => {setModalType({table: "periodic", type: "delete"})
                                        setValueToModify({[key]: value});
                                        setData(Object.keys(periodicData).map((key) => parseFloat(key)))
                                    }}
                                />
                            </div>
                        </td>
                        <td className="p-3 text-center border border-gray-300">
                            {key + " days"}
                        </td>
                        <td className="p-3 text-center border border-gray-300 text-xl font-bold">
                            {value as string}
                        </td>
                    </tr>
                ))
            }
            </tbody>
            </table>
            </div>
        </div>

        <div>
            <div className="overflow-x-auto">
            <table className="min-w-full bg-white border border-gray-300">
            <thead>
            <tr className="bg-gray-200">
            <th className="p-3 text-center border border-gray-300" colSpan={6}>Mechanical and geophysical offsets</th>
            <th className="p-3 text-center border border-gray-300">
                <div className="flex flex-row justify-center items-center gap-4">
                <PlusIcon className="size-6 hover:text-green-600 cursor-pointer"
                    onClick={() => {setModalType({table: "jumps", type: "add"})
                    setData(jumpsData);
                }}
                />
                <ArrowPathIcon className="size-6 hover:text-black cursor-pointer"
                    onClick={() => {setModalType({table: "jumps", type: "reset"})}}
                />
                </div>    
            </th>
            </tr>
            <tr className="bg-gray-100">
            <th className="p-3 text-center border border-gray-300">Edit</th>
            <th className="p-3 text-center w-64 border border-gray-300">Date</th>
            <th className="p-3 text-center w-24 border border-gray-300">FIT</th>
            <th className="p-3 text-center w-48 border border-gray-300">Type</th>
            <th className="p-3 text-center w-32 border border-gray-300">Relaxation</th>
            <th className="p-3 text-center w-32 border border-gray-300">Action</th>
            <th className="p-3 text-center border border-gray-300">Comments</th>
            </tr>
            </thead>
            <tbody>
            {jumpsData?.map((jumpData: ConfigJumpData, idx) => (
            <tr key={idx} className={chosenRowColor(jumpData.action)}>

                <td className="p-3 text-center border border-gray-300 align-middle">
                    <div className="flex justify-center gap-2">
                        {   jumpData.action === "-"  &&
                            <XMarkIcon className="size-6 hover:text-red-500 cursor-pointer"
                            onClick={() => {
                                setModalType({table: "jumps", type: "delete"});
                                setValueToModify(jumpData);
                                setData(jumpsData);
                            }}
                            />
                        }
                        {   (jumpData.action === "A" || jumpData.action === "+") &&
                            <MinusIcon className="size-6 hover:text-red-500 cursor-pointer"
                            onClick={() => {
                                setModalType({table: "jumps", type: "deactivate"});
                                setValueToModify(jumpData);
                                setData(jumpsData);
                            }}
                            />
                        }
                        {   jumpData.action === "-" &&
                            <PlusIcon className="size-6 hover:text-green-600 cursor-pointer"
                            onClick={() => {
                                setModalType({table: "jumps", type: "activate"});
                                setValueToModify(jumpData);
                                setData(jumpsData);
                            }}
                            />
                        }
                        
                    </div>
                </td>
                <td className="p-3 text-center border border-gray-300">
                    {formatDate(jumpData.Year, jumpData.DOY)}
                </td>
                <td className="p-3 text-center border border-gray-300">
                    {jumpData.fit ? "YES" : "NO"}
                </td>
                <td className="p-3 text-center border border-gray-300">
                    {jumpData.type_name}
                </td>
                <td className="p-3 text-center border border-gray-300">
                    {jumpData.relaxation && jumpData.relaxation.length > 0 ? getRelaxation(jumpData.relaxation) : "-"} 
                </td>
                <td className="p-3 text-center border border-gray-300">
                    {jumpData.action ? jumpData.action : "-"} 
                </td>
                <td className="p-3 text-center border border-gray-300" title={jumpData.metadata}>
                    <div dangerouslySetInnerHTML={{ __html: jumpData.metadata ? jumpData.metadata : "-" }} />
                </td>
            </tr>
            ))}
            </tbody>
            </table>
            </div>
        </div>
        {
         modals && modals?.title === "TimeSeriesConfigModal" &&
            <TimeSeriesConfigModal type= {modalType} valueToModify={valueToModify} data= {data} stationId = {stationId} refetch = {refetch}
            success = {success} setSuccess = {setSuccess} jumpTypes = {jumpTypes} solution = {solution} stack = {stack}
            />
        }
        { 
        modals && modals?.title === "ConfirmDelete" && 
            <ConfirmDeleteModal
                confirmRemove={modalType?.type === "reset" ? resetData : modalType?.type === "deactivate" ? 
                deactivateRow : deleteRow}
                closeModal={() => {
                    if(msg && apiOkStatuses.includes(msg.status)){
                        refetch();
                    }
                    setModals(undefined)
                    setModalType(undefined)
                    setMsg(undefined)
                }}
                loading={loadingConfirmModal}
                type = {modalType?.type}
                msg = {msg}
            />
        }
        
    </div>
    );
}
 
export default TimeSeriesParams;