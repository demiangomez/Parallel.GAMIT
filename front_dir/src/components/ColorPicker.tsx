import { useEffect } from 'react';
import{ ColorData } from "@types"
interface ColorPickerProps { 
    colores: ColorData[];
    oldColor?: ColorData;
    colorPicked: ColorData;
    setColorPicked: (color: ColorData) => void;
}

const ColorPicker = ({colores, oldColor, colorPicked, setColorPicked}: ColorPickerProps
) => {

    const handleChangeComplete = (pickedColor: ColorData) => {
        setColorPicked(pickedColor);
    };
    
    useEffect(() => {
        if(oldColor){
            setColorPicked(oldColor);
        }
    },[oldColor]);


    const divClass = (color: string) =>{
        if(color === colorPicked.color){
            return {width: '100px', height: '100px', backgroundColor: '#000', borderRadius: '50%' , border: '4px solid #fff' }
        }
        else{
            return {width: '100px', height: '100px', backgroundColor: '#000', borderRadius: '50%'}
        }
    }

    const labelClass = (color: string) =>{
        if(color === colorPicked.color){
            return "text text-lg "
        }
        else{
            return "text text-lg text-gray-500"
        }
    }

    return (
        <div className="flex flex-row items-center justify-center gap-5 flex-wrap">
            {
                colores && colores.map((color: ColorData, idx: any) => {
                    return(      
                    <div key={idx } className='flex flex-col items-center justify-center gap-2'
                        onClick={() => handleChangeComplete(color)}
                    >
                        <div className={color.color} style={divClass(color.color)}>
                        </div>
                        <div>
                            <label className={labelClass(color.color)}>
                                {color && color && 
                                color.color.replace('-icon', '').replace('-',' ').replace(color.color.charAt(0),color.color.charAt(0).toUpperCase())}</label>
                        </div>
                    </div>
                )})
            }
        </div>
    );
};

export default ColorPicker;