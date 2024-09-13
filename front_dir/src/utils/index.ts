import { TokenPayload } from "@types";

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
    const formattedDate = date?.toLocaleString("en-US", datesFormatOpt);
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

export const isValidDate = (dateString: string) => {
    const date = new Date(dateString);
    return !isNaN(date.getTime());
};

export const dateToUTC = (date: Date | string) => {
    const now = new Date(date);
    const utc = new Date(now.getTime() + now.getTimezoneOffset() * 60000);
    return utc;
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

    const date = new Date(
        `${year}-01-01T${formattedHours}:${formattedMinutes}:${formattedSeconds}Z`,
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
