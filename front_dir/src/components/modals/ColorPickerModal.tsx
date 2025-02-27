import { ColorPicker, Modal } from "@componentsReact";
import { FormReducerAction } from '@hooks/useFormReducer';
import { ColorData} from "@types"
import { useEffect, useState } from "react";

interface ColorPickerModalProps {
    dispatch: React.Dispatch<FormReducerAction>
    closeModal  : () => void
    colores: ColorData[]
    changeColorIdToString: (e: number) => void
    formstate: any 
    type: "add" | "edit" | "none"
}

const ColorPickerModal = ({dispatch, closeModal, colores, changeColorIdToString, formstate, type}: ColorPickerModalProps) => {
    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setOldColor(colorPicked);
        dispatch({
            type: "change_value",
            payload: {
                inputName: "color",
                inputValue: colorPicked.id,
            },
        })
        dispatch({
            type: "change_value",
            payload: {
                inputName: "color_name",
                inputValue: colorPicked.color,
            },
        })
        changeColorIdToString(colorPicked.id);
        closeModal();
    }

    const [oldColor, setOldColor] = useState<ColorData | undefined>(undefined);

    const [colorPicked, setColorPicked] = useState<ColorData>({id: 1, color: "green-icon"});

    useEffect(() => {
        if(type === "edit" && formstate && formstate.color &&  oldColor === undefined){
            const colorSeted = {id: formstate.color, color: formstate.color_name }
            setOldColor(colorSeted);
        }
    }, [type]);

    

    return (  

        <Modal modalId="ColorPicker" size="sm" close={true} handleCloseModal={closeModal}>
            <form action="" className="flex flex-col items-center justify-center gap-4" onSubmit={(e) => handleSubmit(e)}>
            <div className="">
                <ColorPicker colores={colores} oldColor ={oldColor} colorPicked={colorPicked} setColorPicked={setColorPicked}/>
            </div>
            <button type="submit" className="btn btn-success btn-md w-[220px]">Save</button>
            </form>
        </Modal>
    );
}
 
export default ColorPickerModal;