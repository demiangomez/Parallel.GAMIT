interface SpinnerProps {
    size: "xs" | "sm" | "md" | "lg";
}

const Spinner = ({ size }: SpinnerProps) => {
    return (
        <span
            className={`loading loading-spinner loading-${size} loading- `}
        ></span>
    );
};

export default Spinner;
