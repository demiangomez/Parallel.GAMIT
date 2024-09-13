const LargeSkeleton = () => {
    return (
        <div className="flex w-full">
            <div className="flex flex-col gap-4 w-11/12 mx-auto my-4 self-center text-center">
                <div className="flex space-x-4">
                    <div
                        className="skeleton h-[130px] w-7/12 self-start"
                        style={{
                            backgroundColor: "rgb(107 114 128 / 0.2)",
                        }}
                    ></div>
                    <div
                        className="skeleton h-[130px] w-5/12 self-start"
                        style={{
                            backgroundColor: "rgb(107 114 128 / 0.2)",
                        }}
                    ></div>
                </div>
                <div
                    className="skeleton h-[200px] w-full"
                    style={{
                        backgroundColor: "rgb(107 114 128 / 0.2)",
                    }}
                ></div>
            </div>
        </div>
    );
};

export default LargeSkeleton;
