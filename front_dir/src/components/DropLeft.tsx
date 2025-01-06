
interface DropLeftProps {
    mapState: boolean;
    setMapState: React.Dispatch<React.SetStateAction<boolean>>; 
    setForceSyncDropLeftMap: React.Dispatch<React.SetStateAction<number>>;
}

const DropLeft = ({mapState, setMapState, setForceSyncDropLeftMap }: DropLeftProps

) => {
    return (
    <div className="z-[1000000] bg-white border-t-2 border-r-2 border-b-2 border-gray-500 h-[70px] w-[40px] absolute rounded-r-full top-1/2 flex items-center justify-center cursor-pointer hover:bg-gray-200"
        onClick={() => { setMapState(!mapState); setForceSyncDropLeftMap((prev) => prev + 1); }}
    >
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-6">
        <path strokeLinecap="round" strokeLinejoin="round" d={mapState? "M15.75 19.5 8.25 12l7.5-7.5" : "m8.25 4.5 7.5 7.5-7.5 7.5"} />
        </svg>
    </div>
    );
}
 
export default DropLeft;