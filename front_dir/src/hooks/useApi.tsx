import axios, { AxiosError, AxiosInstance } from "axios";

const BASEURL: string = import.meta.env.VITE_API_URL;

export default function useApi(
    token: string | null,
    logout: (href: boolean) => void,
): AxiosInstance {
    const axiosInstance = axios.create({
        baseURL: BASEURL,
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token ?? ""}`,
        },
    });

    axiosInstance.interceptors.response.use(
        (response) => {
            // basurrrraaa
            if (response.status === 200) {
                response.data.statusCode = response.status;
            }
            if (response.status === 201) {
                response.data.statusCode = response.status;
            }
            if (response.status === 204) {
                response.data = {
                    msg: "Deleted Succesfully",
                    response: "",
                    status: "success",
                    statusCode: response.status,
                };
            }
            return response;
        },

        (error: AxiosError) => {
            const status = error.response ? error.response.status : null;
            if (status === 401) {
                logout(false);
            }
            const requestResponse: XMLHttpRequest = error.request;
            return {
                data: {
                    msg: error.message,
                    response: error.response?.data,
                    status: "error",
                    statusCode: requestResponse.status,
                },
            };
        },
    );

    return axiosInstance;
}
