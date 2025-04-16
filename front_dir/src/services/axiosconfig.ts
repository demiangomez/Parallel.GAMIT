import axios from "axios";
const BASEURL: string = import.meta.env.VITE_API_URL;

const axiosInstanceUnauth = axios.create({
    baseURL: BASEURL,
    headers: {
        "Content-Type": "application/json",
    },
});

export { axiosInstanceUnauth };
