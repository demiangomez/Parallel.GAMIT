interface TableSkeletonProps {
    titleSize?: string;
    mainSize?: string;
}

const TableSkeleton = ({ titleSize, mainSize }: TableSkeletonProps) => {
    return (
        <div className="flex flex-col">
            <div
                className={`skeleton w-5/12 self-center`}
                style={{ height: titleSize ? titleSize : "0px" }}
            >
                {" "}
            </div>
            <div
                className={`skeleton mt-4 w-full`}
                style={{ height: mainSize ? mainSize : "400px" }}
            >
                {" "}
            </div>
        </div>
    );
};

export default TableSkeleton;
