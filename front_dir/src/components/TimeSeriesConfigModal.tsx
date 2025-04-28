import { Modal, Alert} from "components"
import { postTimeSeriesPolynomialService, postTimeSeriesPeriodicService, postTimeSeriesJumpService} from "@services";
import React, { useState ,useEffect } from 'react';
import { useFormReducer, useApi, useAuth } from "@hooks/index";
import { SERIES_JUMP_DATA, SERIES_POLYNOMIAL_DATA, SERIES_PERIODIC_DATA } from "@utils/reducerFormStates";
import { apiOkStatuses } from "@utils";
import { Errors, JumpType} from "@types";

interface TimeSeriesConfigModalProps{
    type: {table: string, type: string} | undefined;
    valueToModify: any
    data: any
    stationId: number
    refetch: () => void
    success: boolean
    setSuccess: (value: boolean) => void
    jumpTypes?: JumpType[]
    solution: string
    stack: string
}

const TimeSeriesConfigModal = ({type, valueToModify, data, stationId, refetch, success, setSuccess, jumpTypes, solution, stack}:TimeSeriesConfigModalProps) => {
    const { token, logout } = useAuth();
    const api = useApi(token, logout);
    const { formState, dispatch } = useFormReducer<Record<string, any>>({});

    const [loading, setLoading] = useState(false);

    const [msg, setMsg] = useState<
            { status: number; msg: string; errors?: Errors } | undefined
    >(undefined);

    const notAllowedKeys = ["fit", "metadata"];
    const handleSubmit = (e: React.FormEvent) =>{
        e.preventDefault()
        setSuccess(true);
        if(type?.type === "add" || type?.type === "edit"){
            postData();
        }
        else if(type?.type === "activate"){
            activateRow()
        }
 
    }

    const getType = () =>{
        if(type?.table === "jumps" && jumpTypes){
            const jumpType = formState.jump_type;
            const type = jumpTypes.find((j: JumpType) => j.type === jumpType);
            if(!type){
                return -1
            }
            return type.id;
        }
        else{
            return -1
        }
    }

    const activateRow = async () => {
        if(valueToModify){
            if(type?.table === "jumps"){
                let relaxation 
                if(getType() >= 1 && Array.isArray(formState.relaxation)){
                    relaxation = formState.relaxation
                }
                else{
                    relaxation = []
                }
                const params = {
                    Year: valueToModify.Year,
                    DOY: valueToModify.DOY,
                    action: "+",
                    jump_type:  Number(getType()),
                    relaxation: relaxation,
                }

                try{
                    setLoading(true);
                    const res = await postTimeSeriesJumpService<any>(api, stationId, solution, stack,params);
                    if ("status" in res) {
                        setMsg({
                            status: res.statusCode,
                            msg: res.response.type,
                            errors: res.response,
                        });
                    } else {
                        setMsg({
                            status: res.statusCode,
                            msg: "Jump row activated successfully",
                        });
                    }
                }
                catch(e){
                    console.error(e);
                }
                finally{
                    setLoading(false);
                }
            }
        }
    }

    const postData= async () =>{
        try{
            setLoading(true);
            let service, chosenMsg, params
            if(type?.table === "jumps" || type?.table === "periodic" || type?.table === "polynomial"){
                if(type?.table === "jumps"){
                    let relaxation 
                    if(getType() >= 1 && Array.isArray(formState.relaxation)){
                        relaxation = formState.relaxation
                    }
                    else{
                        relaxation = []
                    }

                    params = Object.entries(formState).reduce(
                        (acc, [key, value]) => {
                            if(key !== "relaxation" && key !== "action" && key !== "jump_type"){
                                return {
                                    ...acc,
                                    [key]: Number((value as string)),
                                };
                            }
                            else if(key === "jump_type"){
                                return {
                                    ...acc,
                                    [key]: (getType() as number),
                                };

                            }
                            else if(key === "relaxation"){
                                return {
                                    ...acc,
                                    [key]: relaxation,
                                };
                            }
                            else{
                                return {
                                    ...acc,
                                    [key]: (value as string),
                                };
                            }
                        },
                        {},
                    ) as any;
                    service = postTimeSeriesJumpService;
                    chosenMsg = "Jump row added successfully"
                }
                else if(type?.table === "periodic"){
                    service = postTimeSeriesPeriodicService;
                    params = { frequencies: [...formState.frequence, ...data] };
                    chosenMsg = "Periodic row added successfully"
                }
                else{
                    service = postTimeSeriesPolynomialService;
                    params = formState;
                    chosenMsg = "Polynomial row edited successfully"
                }
                
                const res = await service<any>(api, stationId, solution, stack, params);
                if ("status" in res) {
                    setMsg({
                        status: res.statusCode,
                        msg: res.response.type,
                        errors: res.response,
                    });
                } else {
                    setMsg({
                        status: res.statusCode,
                        msg: chosenMsg,
                    });
                }
            }
        }
        catch(e){
            console.error(e);
        }
        finally{
            setLoading(false);
        }
    }

    

    const handleClose = () =>{
        if(success){
            refetch();
        }
        setMsg(undefined);
    }


    useEffect(() =>{
        if(type?.table && type.type ){
            if(type.type === "add"){
                switch(type.table){
                    case "polynomial":
                        dispatch({
                            type: "set",
                            payload: SERIES_POLYNOMIAL_DATA
                        })
                        break;
                    case "periodic":
                        dispatch({
                            type: "set",
                            payload: SERIES_PERIODIC_DATA
                        })
                        break;
                    case "jumps":
                        dispatch({
                            type: "set",
                            payload: SERIES_JUMP_DATA
                        })
                        break;
                }
                dispatch({
                    type: "change_value",
                    payload: {
                        inputName: "action",
                        inputValue: "+"
                    }
                })
            }
            else if(type.type === "edit"){
                dispatch({
                    type: "set",
                    payload:{
                        ...Object.keys(valueToModify).reduce<Record<string, any>>((acc, key) => {
                            if (!notAllowedKeys.includes(key)) {
                                acc[key] = String(valueToModify[key]);
                            }
                            return acc;
                        }, {})
                    }
                })
            }
            else if(type.type === "activate"){
                dispatch({
                    type: "set",
                    payload: {
                        jump_type: "",
                        relaxation: ""
                    }
                })
            }
        }
    }, [type])

    return (  
        <Modal modalId="TimeSeriesConfigModal" close={false} size="smPlus" handleCloseModal={handleClose}>
            <div className="w-full flex grow mb-2">
            <h3 className="font-bold text-center text-2xl my-2 w-full self-center" >
                {type?.type === "edit" ? "Edit" : type?.type === "activate" ? "Activate" : "Add"}
            </h3>
            </div>
            <form className="form-control space-y-4" onSubmit={handleSubmit}>
            <div className="form-control space-y-4">
                {Object.keys(formState).map((key, idx) => (
                !notAllowedKeys.includes(key) && (key !== "frequence") && (key !== "relaxation") && (key !== "action") && (key !== "jump_type") ? (
                    <label
                    key={`${key}-${idx}`}
                    className={`w-full input input-bordered flex items-center justify-center gap-2 h-16`}
                    title={"globalDescription"}
                    >
                    <div className="label">
                        <span className="font-bold">
                        {key.toUpperCase().split('_').join(' ')}
                        </span>
                    </div>
                    <input
                        type="text"
                        value={formState[key] || ""}
                        className="grow text-left"
                        onChange={(e) => {
                        const changeValue = e.target.value;
                        dispatch({
                            type: "change_value",
                            payload: {
                            inputName: key,
                            inputValue: changeValue
                            }
                        });
                        }}
                    />
                    </label>
                ) :
                ((key === "frequence" && type?.table === "periodic") || (key === "relaxation" && type?.table === "jumps" && (getType() >= 1))) ? (
                    <div key={idx} className="space-y-4 flex flex-col items-center justify-center">
                    <div className="flex items-center justify-center gap-2 w-full">
                        <input
                        type="number"
                        step="0.01"
                        placeholder={type.table === "periodic" ? "Enter frequency value" : "Enter relaxation value"}
                        className="input input-bordered grow text-left h-16"
                        id="frequencyInput"
                        />
                        <button
                        type="button"
                        className="btn h-16"
                        onClick={() => {
                            const input = document.getElementById('frequencyInput') as HTMLInputElement;
                            const value = parseFloat(input.value);
                            if (!isNaN(value)) {
                            if(type.table === "periodic"){
                                const currentFrequences = Array.isArray(formState.frequence) 
                                ? formState.frequence 
                                : [];
                                dispatch({
                                type: "change_value",
                                payload: {
                                    inputName: "frequence",
                                    inputValue: [...currentFrequences, value]
                                }
                                });
                                input.value = '';
                            }
                            else if(type.table === "jumps"){
                                const currentFrequences = Array.isArray(formState.relaxation) 
                                ? formState.relaxation 
                                : [];
                                dispatch({
                                type: "change_value",
                                payload: {
                                    inputName: "relaxation",
                                    inputValue: [...currentFrequences, value]
                                }
                                });
                                input.value = '';
                            }
                            }
                        }}
                        >
                        {type.table === "periodic" ? "Add Frequency" : "Add Relaxation Years"}
                        </button>
                    </div>
                    <div className="max-h-44 flex flex-wrap gap-3 justify-start items-center overflow-y-auto w-full p-2">
                        {Array.isArray(formState.relaxation) &&
                            <label className="font-bold text-lg">Years:</label>
                        }
                        {Array.isArray(formState.frequence) && formState.frequence.map((freq: number, i: number) => (
                        <div key={i} className="flex flex-row justify-between items-center badge badge-primary gap-2 p-4">
                            {freq}
                            <button
                            type="button"
                            className="btn btn-xs btn-ghost"
                            onClick={() => {
                                const newFrequences = formState.frequence.filter((_: number, index: number) => index !== i);
                                dispatch({
                                type: "change_value",
                                payload: {
                                    inputName: "frequence",
                                    inputValue: newFrequences
                                }
                                });
                            }}
                            >
                            ✕
                            </button>
                        </div>
                        ))}
                        {Array.isArray(formState.relaxation) && formState.relaxation.map((freq: number, i: number) => (
                        <div key={i} className="flex flex-row justify-between items-center badge badge-primary gap-2 m-1 p-4">
                            {freq}
                            <button
                            type="button"
                            className="btn btn-xs btn-ghost"
                            onClick={() => {
                                const newFrequences = formState.relaxation.filter((_: number, index: number) => index !== i);
                                dispatch({
                                type: "change_value",
                                payload: {
                                    inputName: "relaxation",
                                    inputValue: newFrequences
                                }
                                });
                            }}
                            >
                            ✕
                            </button>
                        </div>
                        ))}
                    </div>
                    </div>
                ) : key === "jump_type" && type?.table === "jumps" ? 
                (
                    <label 
                        className="w-full input input-bordered flex items-center justify-center gap-2 h-16 cursor-pointer"
                        onClick={(e) => {
                            const select = e.currentTarget.querySelector('select');
                            if (select) {
                                select.focus();
                                select.click();
                            }
                        }}
                    >
                        <div className="label">
                            <span className="font-bold">JUMP TYPE</span>
                        </div>
                        <select 
                            className="grow text-left outline-none cursor-pointer"
                            value={formState.jump_type || ""}
                            onChange={(e) => {
                                dispatch({
                                    type: "change_value",
                                    payload: {
                                        inputName: "jump_type",
                                        inputValue: e.target.value
                                    }
                                });
                            }}
                        >
                            <option value="">Select jump type</option>
                            {jumpTypes?.map((jumpType) => (
                                <option key={jumpType.id} value={jumpType.type}>
                                    {jumpType.type}
                                </option>
                            ))}
                        </select>
                    </label>
                ) : null
                
                ))}
            </div>
            {false && (
                <div className="w-8/12 self-center text-center">
                File upload progress
                <progress
                    value={0}
                    max="100"
                ></progress>
                <span
                    id="progress-value"
                    className="font-semibold"
                ></span>
                </div>
            )}
            
            <button
                className="btn btn-success self-center w-3/12"
                disabled={
                apiOkStatuses.includes(Number(msg?.status))
                }
                type="submit"
            >
                {loading && (
                    <span className="loading loading-spinner loading-sm self-center"></span>
                )}
                {" "}
                Save{" "}
            </button>
            <div className="px-4 w-full self-center">
                <Alert msg={msg} />
            </div> 
            </form>
        </Modal>
    );
}
 
export default TimeSeriesConfigModal;