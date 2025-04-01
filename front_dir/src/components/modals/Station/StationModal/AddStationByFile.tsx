import { Dropzone, Spinner} from "@components/index";
import { useState } from "react";


interface AddStationByFileProps{
    handleCancel: () => void;
}

const AddStationByFile = ({handleCancel}: AddStationByFileProps) => {
    const [file, setFile] = useState<File | undefined>(undefined);
    const [success, setSuccess] = useState<boolean>(false);
    const [loading, setLoading] = useState<boolean>(false);
    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setSuccess(true);
        postStationByFile();
    };

    const postStationByFile = async () => {
        try{
            setLoading(true)
        }
        catch (error){
            console.error(error)
        }
        finally{
            setLoading(false)
        }
    }
    return (  
        <form onSubmit={(e) => handleSubmit(e)} className="flex flex-col items-center justify-center gap-4">
            <Dropzone
            setFile={setFile}
            file={file}
            />
            <div className="flex flex-row A-center justify-center gap-6">
                <button className="btn btn-lg btn-success"
                    disabled={file === undefined || success}
                    type="submit"
                >
                    Create
                    {loading && <Spinner size="md" /> }
                </button>
                <button className="btn btn-lg btn-error"
                    onClick={handleCancel}
                >
                    Cancel
                </button>
            </div>
        </form>
    );
}
 
export default AddStationByFile;