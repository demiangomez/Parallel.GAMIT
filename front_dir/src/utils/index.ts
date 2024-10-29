import { GapData, StationData, TokenPayload } from "@types";

export const modalSizes = {
    sm: "500px",
    smPlus: "45%",
    md: "60%",
    lg: "70%",
    xl: "80%",
    fit: "fit-content",
};

export const apiOkStatuses = [200, 201, 204];

export const apiErrorStatuses = [400, 401, 403, 404, 405, 406, 415, 500];

export const datesFormatOpt: Intl.DateTimeFormatOptions = {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "UTC",
};

export const formattedDates = (date: Date | string | undefined) => {
    if (!date) return;

    const formattedDate = new Intl.DateTimeFormat(
        "en-US",
        datesFormatOpt,
    ).format(new Date(date));
    return formattedDate;
};

export const adjustToLocalTimezone = (dateString: string) => {
    const localDate = new Date(dateString);
    const timezoneOffset = localDate.getTimezoneOffset();
    const adjustedDate = new Date(localDate.getTime() + timezoneOffset * 60000);
    return adjustedDate;
};

export const validateFields = (
    object: Record<string, string | number | boolean | null>,
) => {
    for (const i in object) {
        if (object[i] === "" || object[i] === null || object[i] === undefined) {
            return false;
        }
    }
    return true;
};

export const isValidNumber = (num: string) => {
    if (num === "") return true;
    const regex = /^(0|[1-9]\d*)(\.\d+)?$/;
    return regex.test(num);
};

export const isValidDate = (dateString: string) => {
    const date = new Date(dateString);
    return !isNaN(date.getTime());
};

export const dateToUTC = (date: Date | string) => {
    const now = new Date(date);
    const utc = new Date(now.getTime() + now.getTimezoneOffset() * 60000);
    return utc;
};

export const ensureEndsWithZ = (str: string): string => {
    return str.endsWith("Z") ? str : str + "Z";
};

export const woTz = (d: Date | undefined) => {
    if (d === undefined) {
        return;
    }

    const tz = d && d?.getTimezoneOffset() * 60000;

    const dateWoTz = d && tz && new Date(d?.getTime() - tz);

    return dateWoTz;
};

export const doyToDate = (doy: string) => {
    const [year, dayOfYear] = doy.split(".");

    const date = new Date(`${year}-01-01`);

    const leapYear =
        (Number(year) % 4 == 0 && Number(year) % 100 != 0) ||
        Number(year) % 400 == 0;

    date.setTime(
        date.getTime() +
            (leapYear
                ? (366 / 1000) * Number(dayOfYear)
                : (365 / 1000) * Number(dayOfYear)) *
                86400000,
    );

    return date;
};

export const dateFromDay = (day: string) => {
    const [year, dayOfYear = "001", hours = "0", minutes = "0", seconds = "0"] =
        day.split(" ");

    // Asegurarse de que el día del año tenga 3 dígitos
    const formattedDayOfYear = dayOfYear?.padStart(3, "0");
    // Asegurarse de que las horas, minutos y segundos tengan 2 dígitos
    const formattedHours = hours.padStart(2, "0");
    const formattedMinutes = minutes.padStart(2, "0");
    const formattedSeconds = seconds.padStart(2, "0");

    const formattedYear = year.padStart(4, "0");
    const date = new Date(
        `${formattedYear}-01-01T${formattedHours}:${formattedMinutes}:${formattedSeconds}Z`,
    );
    // Corrección: Sumar los días como milisegundos al 1 de enero del año dado
    date.setTime(date.getTime() + (Number(formattedDayOfYear) - 1) * 86400000);
    return date;
};

export const dayFromDate = (date: Date | string) => {
    if (date === null) {
        return null;
    }

    const dateObj = new Date(date);
    const startOfYear = new Date(Date.UTC(dateObj.getUTCFullYear(), 0, 1));
    const diff = dateObj.getTime() - startOfYear.getTime();
    const oneDay = 86400000; // milisegundos en un día
    const dayOfYear = Math.floor(diff / oneDay) + 1; // +1 porque el día 1 del año es 1, no 0

    const year = isNaN(dateObj.getUTCFullYear())
        ? ""
        : dateObj.getUTCFullYear();
    const day = isNaN(dayOfYear) ? "" : dayOfYear;
    const hours = isNaN(dateObj.getUTCHours()) ? "" : dateObj.getUTCHours();
    const minutes = isNaN(dateObj.getUTCMinutes())
        ? ""
        : dateObj.getUTCMinutes();
    const seconds = isNaN(dateObj.getUTCSeconds())
        ? ""
        : dateObj.getUTCSeconds();

    return `${year} ${day} ${hours} ${minutes} ${seconds}`;
    // return `${
    //     isNaN(dateObj.getUTCFullYear())
    //         ? new Date().getUTCFullYear()
    //         : dateObj.getUTCFullYear()
    // } ${
    //     isNaN(dayOfYear)
    //         ? Math.floor(
    //               (now.getTime() -
    //                   new Date(
    //                       Date.UTC(now.getUTCFullYear(), 0, 1),
    //                   ).getTime()) /
    //                   86400000,
    //           ) + 1
    //         : dayOfYear
    // }`;
};

export const generateErrorMessages = (station: StationData) => {
    const errorMessages: string[] = [];

    if (!station.has_stationinfo) {
        errorMessages.push("Station has no station information records!");
    }

    if (station.gaps && station.gaps.length !== 0) {
        station?.gaps?.forEach((gap: GapData) => {
            const {
                record_start_date_start,
                record_end_date_end,
                record_end_date_start,
                record_start_date_end,
                rinex_count,
            } = gap;

            if (record_start_date_start && record_end_date_end) {
                errorMessages.push(
                    `At least ${rinex_count} RINEX file(s) outside of station info record ending at ${formattedDates(new Date(record_end_date_end))} and next record starting at ${formattedDates(new Date(record_start_date_start))}`,
                );
            } else if (
                record_start_date_start &&
                !record_end_date_end &&
                !record_end_date_start
            ) {
                errorMessages.push(
                    `At least ${rinex_count} RINEX file(s) outside of station info record starting at ${formattedDates(new Date(record_start_date_start))}`,
                );
            } else if (
                record_end_date_end &&
                !record_start_date_end &&
                !record_start_date_start
            ) {
                errorMessages.push(
                    `At least ${rinex_count} RINEX file(s) outside of station info record ending at ${formattedDates(new Date(record_end_date_end))}`,
                );
            }
        });
    }

    return errorMessages;
};

export const transformParams = (params: any) => {
    return Object.entries(params)
        .map(([key, value]) => `${key}=${value}`)
        .join("&");
};

export const jwtDeserializer = (token: string) => {
    if (token) {
        const tokenPayload = JSON.parse(
            atob(token.split(".")[1]),
        ) as TokenPayload;
        return tokenPayload;
    }
};

export const showModal = (title: string) => {
    const modal = document.getElementById(title + "-modal") as HTMLFormElement;
    if (modal) {
        modal.showModal();
    }
};

export const decimalToDMS = (coordinate: number, isLatitude: boolean) => {
    const absolute = Math.abs(coordinate);
    const degrees = Math.floor(absolute);
    const minutesDecimal = (absolute - degrees) * 60;
    const minutes = Math.floor(minutesDecimal);
    const seconds = (minutesDecimal - minutes) * 60;

    const direction = isLatitude
        ? coordinate >= 0
            ? "N"
            : "S"
        : coordinate >= 0
          ? "E"
          : "W";

    return `${degrees}°${minutes}'${seconds.toFixed(4)}"${direction}`;
};

export const rinexMockup = {
    data: [
        {
            related_station_info: [
                {
                    date_start: "2024-01-01",
                    date_end: "2024-01-02",
                },
                {
                    date_start: "2024-01-03",
                    date_end: "2024-01-04",
                },
            ],
            rinex: [
                {
                    related_station_info: [
                        {
                            date_start: "2024-01-01",
                            date_end: "2024-01-02",
                        },
                    ],
                    rinex: [
                        {
                            network_code: "sag",
                            station_code: "ceca",
                            has_station_info: false,
                            has_multiple_station_info_gap: false,
                            metadata_mismatch: false,
                            gap_type: null,
                            year: null,
                            doy: null,
                            timestamp_start: null,
                            timestamp_end: null,
                            receiver: null,
                            rx_sn: null,
                            rx_firm: null,
                            antenna: null,
                            ant_sn: null,
                            dome: null,
                            offset: null,
                            int: null,
                            comp: 0.9,
                        },
                        {
                            network_code: "sag",
                            station_code: "ceca",
                            has_station_info: false,
                            has_multiple_station_info_gap: false,
                            metadata_mismatch: false,
                            gap_type: "AFTER LAST STATIONINFO",
                            year: null,
                            doy: null,
                            timestamp_start: null,
                            timestamp_end: null,
                            receiver: null,
                            rx_sn: null,
                            rx_firm: null,
                            antenna: null,
                            ant_sn: null,
                            dome: null,
                            offset: null,
                            int: null,
                            comp: 0.81,
                        },
                    ],
                },
            ],
        },
        {
            related_station_info: [
                // STATIONS INFOS QUE ABARCA EL PRIMER GRUPO
                {
                    date_start: "2024-01-01",
                    date_end: "2024-01-02",
                },
                {
                    date_start: "2024-01-03",
                    date_end: "2024-01-04",
                },
            ],
            rinex: [
                {
                    // C/OBJETO CORRESPONDE AL SEGUNDO GRUPO, PUEDE TENR MAS DE UN RINEX ASOCIADO AL STATION INFO
                    related_station_info: [
                        {
                            date_start: "2024-01-01",
                            date_end: "2024-01-02",
                        },
                    ],
                    rinex: [
                        {
                            network_code: "sag",
                            station_code: "ceca",

                            has_station_info: true,
                            metadata_mismatch: false,
                            has_multiple_station_info_gap: false,
                            gap_type: null,

                            year: null,
                            doy: null,
                            timestamp_start: null,
                            timestamp_end: null,
                            receiver: null,
                            rx_sn: null,
                            rx_firm: null,
                            antenna: null,
                            ant_sn: null,
                            dome: null,
                            offset: null,
                            int: null,
                            comp: 0.7,
                        },
                        {
                            network_code: "sag",
                            station_code: "ceca",

                            has_station_info: false,
                            metadata_mismatch: false,
                            has_multiple_station_info_gap: false,
                            gap_type: "AFTER LAST STATIONINFO",

                            year: null,
                            doy: null,
                            timestamp_start: null,
                            timestamp_end: null,
                            receiver: null,
                            rx_sn: null,
                            rx_firm: null,
                            antenna: null,
                            ant_sn: null,
                            dome: null,
                            offset: null,
                            int: null,
                            comp: 0.86,
                        },
                        {
                            network_code: "sag",
                            station_code: "ceca",
                            has_station_info: false,
                            metadata_mismatch: false,
                            has_multiple_station_info_gap: false,
                            gap_type: "BEFORE FIRST STATIONINFO",
                            year: null,
                            doy: null,
                            timestamp_start: null,
                            timestamp_end: null,
                            receiver: null,
                            rx_sn: null,
                            rx_firm: null,
                            antenna: null,
                            ant_sn: null,
                            dome: null,
                            offset: null,
                            int: null,
                            comp: 0.1,
                        },
                    ],
                },
                {
                    related_station_info: [
                        {
                            date_start: "2024-01-01",
                            date_end: "2024-01-02",
                        },
                    ],
                    rinex: [
                        {
                            network_code: "sag",
                            station_code: "ceca",
                            has_station_info: false,
                            has_multiple_station_info_gap: false,
                            metadata_mismatch: false,
                            gap_type: null,
                            year: null,
                            doy: null,
                            timestamp_start: null,
                            timestamp_end: null,
                            receiver: null,
                            rx_sn: null,
                            rx_firm: null,
                            antenna: null,
                            ant_sn: null,
                            dome: null,
                            offset: null,
                            int: null,
                            comp: 0.7,
                        },
                        {
                            network_code: "sag",
                            station_code: "ceca",
                            has_station_info: false,
                            has_multiple_station_info_gap: false,
                            metadata_mismatch: false,
                            gap_type: "BEFORE FIRST STATIONINFO",
                            year: null,
                            doy: null,
                            timestamp_start: null,
                            timestamp_end: null,
                            receiver: null,
                            rx_sn: null,
                            rx_firm: null,
                            antenna: null,
                            ant_sn: null,
                            dome: null,
                            offset: null,
                            int: null,
                            comp: 0.5,
                        },
                    ],
                },
            ],
        },
        {
            related_station_info: [
                {
                    date_start: "2024-01-01",
                    date_end: "2024-01-02",
                },
                {
                    date_start: "2024-01-03",
                    date_end: "2024-01-04",
                },
            ],
            rinex: [
                {
                    related_station_info: [
                        {
                            date_start: "2024-01-01",
                            date_end: "2024-01-02",
                        },
                    ],
                    rinex: [
                        {
                            network_code: "sag",
                            station_code: "ceca",
                            has_station_info: true,
                            has_multiple_station_info_gap: true,
                            metadata_mismatch: false,
                            gap_type: null,
                            year: null,
                            doy: null,
                            timestamp_start: null,
                            timestamp_end: null,
                            receiver: null,
                            rx_sn: null,
                            rx_firm: null,
                            antenna: null,
                            ant_sn: null,
                            dome: null,
                            offset: null,
                            int: null,
                            comp: 0.3,
                        },
                    ],
                },
            ],
        },
        {
            related_station_info: [
                {
                    date_start: "2024-01-01",
                    date_end: "2024-01-02",
                },
                {
                    date_start: "2024-01-03",
                    date_end: "2024-01-04",
                },
            ],
            rinex: [
                {
                    related_station_info: [
                        {
                            date_start: "2024-01-01",
                            date_end: "2024-01-02",
                        },
                    ],
                    rinex: [
                        {
                            network_code: "sag",
                            station_code: "ceca",
                            has_station_info: false,
                            has_multiple_station_info_gap: false,
                            metadata_mismatch: false,
                            gap_type: "AFTER LAST STATIONINFO",
                            year: null,
                            doy: null,
                            timestamp_start: null,
                            timestamp_end: null,
                            receiver: null,
                            rx_sn: null,
                            rx_firm: null,
                            antenna: null,
                            ant_sn: null,
                            dome: null,
                            offset: null,
                            int: null,
                            comp: 0.4,
                        },
                    ],
                },
            ],
        },
    ],
};
