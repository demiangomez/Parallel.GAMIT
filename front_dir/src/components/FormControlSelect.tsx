interface Props {
    title: string;
    options: string[];
    optionSelected: string;
    optionDisabled?: string;
    selectFunction: (option: string) => void;
}

const FormControlSelect = ({
    title,
    options,
    optionSelected,
    optionDisabled,
    selectFunction,
}: Props) => {
    return (
        <label className="form-control">
            <div className="label">
                <span className="text-lg font-semibold "> {title}</span>
            </div>
            <select
                className="select select-bordered"
                onChange={(e) => selectFunction(e.target.value)}
            >
                {options.map((option, index) => {
                    return (
                        <option
                            key={index}
                            defaultValue={optionSelected}
                            disabled={option === optionDisabled}
                            value={option}
                        >
                            {option}
                        </option>
                    );
                })}
            </select>
        </label>
    );
};

export default FormControlSelect;
