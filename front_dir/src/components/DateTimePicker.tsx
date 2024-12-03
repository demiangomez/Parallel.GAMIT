import { woTz } from "@utils";
import { FormReducerAction } from "@hooks/useFormReducer";

interface DatetimePickerProps {
    typeKey: string;
    startDate: Date | null;
    endDate: Date | null;
    setStartDate: React.Dispatch<React.SetStateAction<Date | null>>;
    setEndDate: React.Dispatch<React.SetStateAction<Date | null>>;
    dispatch: (value: FormReducerAction) => void;
}

const DateTimePicker = ({
    typeKey,
    startDate,
    setStartDate,
    endDate,
    setEndDate,
    dispatch,
}: DatetimePickerProps) => {
    const CustomTimeInput = ({
        date,
        typeKey,
        onChangeCustom,
    }: {
        date: Date | null;
        typeKey: string;
        onChangeCustom: (date: Date, time: string, typeKey: string) => void;
    }) => {
        const defaultTime = typeKey === "date_end" ? "23:59:59" : "00:00:00";
        const value =
            date instanceof Date
                ? date.toLocaleTimeString("it-IT")
                : defaultTime;
        return (
            <input
                type="time"
                step="1"
                value={value}
                onChange={(e) =>
                    onChangeCustom(date ?? new Date(), e.target.value, typeKey)
                }
            />
        );
    };

    const handleChangeTime = (date: Date, time: string, typeKey: string) => {
        const [hh, mm, ss] = time.split(":");
        const targetDate = date instanceof Date ? date : new Date();
        targetDate.setHours(Number(hh || 0), Number(mm || 0), Number(ss || 0));

        if (typeKey === "date_start") {
            setStartDate(targetDate);
        } else {
            setEndDate(targetDate);
        }

        const timeWoTZ = new Date(woTz(date) ?? "").toISOString();

        dispatch({
            type: "change_value",
            payload: {
                inputName: typeKey,
                inputValue: timeWoTZ,
            },
        });
    };

    const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const targetIsoDate =
            (e.target.value !== ""
                ? e.target.value
                : typeKey === "date_start" && startDate
                  ? startDate.toISOString().split("T")[0]
                  : typeKey === "date_end" && endDate
                    ? endDate.toISOString().split("T")[0]
                    : "") +
            (typeKey === "date_start" ? "T00:00:00" : "T23:59:59");

        const newDate = new Date(targetIsoDate);

        if (newDate) {
            if (typeKey === "date_start") {
                setStartDate(newDate);
            } else {
                setEndDate(newDate);
            }

            const dateWoTZ = new Date(woTz(newDate) ?? "").toISOString();
            dispatch({
                type: "change_value",
                payload: {
                    inputName: typeKey,
                    inputValue: dateWoTZ,
                },
            });
        }
    };

    const formattedDates = (date: Date) => {
        const wotzDate = woTz(date);

        if (wotzDate !== 0) {
            return wotzDate?.toISOString().split("T")[0];
        }
    };

    return (
        <>
            <div className="badge badge-ghost">
                <input
                    type="date"
                    defaultValue={
                        typeKey === "date_start" && startDate
                            ? formattedDates(startDate)
                            : typeKey === "date_end" && endDate
                              ? formattedDates(endDate)
                              : ""
                    }
                    onChange={handleDateChange}
                />
            </div>

            <div className="badge badge-ghost">
                <CustomTimeInput
                    date={typeKey === "date_start" ? startDate : endDate}
                    onChangeCustom={handleChangeTime}
                    typeKey={typeKey}
                />
            </div>
        </>
    );
};

export default DateTimePicker;
