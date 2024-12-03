const Skeleton = () => {
    return (
        <div className="flex w-full">
            <div
                className="skeleton h-[70%] ml-4 self-center mb-32 w-1/12"
                style={{
                    backgroundColor: "rgb(107 114 128 / 0.2)",
                }}
            ></div>
            <div className="flex flex-col gap-4 w-7/12 mx-auto mb-32 self-center text-center">
                <div className="flex flex-col space-y-4">
                    <div
                        className="skeleton h-12 self-center w-4/12"
                        style={{
                            backgroundColor: "rgb(107 114 128 / 0.2)",
                        }}
                    ></div>
                    <div
                        className="skeleton h-6 w-3/12 self-center"
                        style={{
                            backgroundColor: "rgb(107 114 128 / 0.2)",
                        }}
                    ></div>
                </div>
                <div
                    className="skeleton h-[400px] w-full"
                    style={{
                        backgroundColor: "rgb(107 114 128 / 0.2)",
                    }}
                ></div>
            </div>
        </div>
    );
};

export default Skeleton;
