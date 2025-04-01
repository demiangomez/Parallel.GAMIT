
interface RinexCompletionPlotProps {
    img: string;
}

const RinexCompletionPlot = ({img}: RinexCompletionPlotProps) => {
    return (  
        <div className="flex flex-col items-center justify-center w-full h-full">
            <h1 className="text-2xl font-bold mb-4">COMPLETION PLOT</h1>
            <img src={img} alt="Completion Plot" className="max-w-full h-auto" />
        </div>
    );
}
 
export default RinexCompletionPlot;