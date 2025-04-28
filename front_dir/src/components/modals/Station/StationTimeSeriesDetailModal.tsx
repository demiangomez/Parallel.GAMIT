import Modal from "../Modal";

const StationTimeSeriesDetailModal = () => {
    return (  
        <Modal
            handleCloseModal={() => {}}
            close = {true}
            modalId="station-time-series-detail-modal"
            size="fit"
        >
            <div className="p-6 space-y-4">
                <h2 className="text-2xl font-bold mb-6">Time Series Reference</h2>
                <div className="space-y-4">
                    <div className="flex items-center text-lg">
                        <div className="w-5 h-5 bg-gray-400 mr-4 rounded-full"></div>
                        <span className="text-gray-700">Deactivated jump or jump not fit</span>
                    </div>
                    <div className="flex items-center text-lg">
                        <div className="w-5 h-5 bg-cyan-400 mr-4 rounded-full"></div>
                        <span className="text-gray-700">Generic mechanical - added by user</span>
                    </div>
                    <div className="flex items-center text-lg">
                        <div className="w-5 h-5 bg-blue-500 mr-4 rounded-full"></div>
                        <span className="text-gray-700">Mechanical - antenna change</span>
                    </div>
                    <div className="flex items-center text-lg">
                        <div className="w-5 h-5 bg-green-500 mr-4 rounded-full"></div>
                        <span className="text-gray-700">PPP only - reference frame change</span>
                    </div>
                    <div className="flex items-center text-lg">
                        <div className="w-5 h-5 bg-red-500 mr-4 rounded-full"></div>
                        <span className="text-gray-700">Geophysical - coseismic + postseismic</span>
                    </div>
                    <div className="flex items-center text-lg">
                        <div className="w-5 h-5 bg-purple-500 mr-4 rounded-full"></div>
                        <span className="text-gray-700">Geophysical - coseismic only</span>
                    </div>
                    <div className="flex items-center text-lg">
                        <div className="w-5 h-5 bg-orange-500 mr-4 rounded-full"></div>
                        <span className="text-gray-700">Geophysical - postseismic only</span>
                    </div>
                </div>
            </div>

        </Modal>
    );
}
 
export default StationTimeSeriesDetailModal;