declare module "@heroicons/*";

export interface GetParams {
    network_code?: string;
    country_code?: string;
    station_code?: string;
    antenna_code?: string;
    offset: number;
    limit: number;
}

export interface TokenPayload {
    token_type: string;
    user_id: number;
    role_id: number;
    role_name: string;
    username: string;
    jti: string;
    iat: number;
    exp: number;
}

export interface ErrorResponse {
    msg: string;
    response: Errors;
    status: string;
    statusCode: number;
}

export interface Errors {
    errors: [{ code: string; detail: string; attr: string }];
    type: string;
}

export interface StationServiceData {
    count: number;
    total_count: number;
    data: StationData[];
    statusCode: number;
}

export interface ExtendedStationInfoData extends StationInfoData {
    statusCode: number;
}

export interface StationInfoServiceData {
    count: number;
    data: StationInfoData[];
    total_count: number;
    statusCode: number;
}

export interface ReceiversServiceData {
    count: number;
    total_count: number;
    data: ReceiversData[];
    statusCode: number;
}

export interface AntennaServiceData {
    count: number;
    total_count: number;
    data: AntennaData[];
    statusCode: number;
}

export interface GamitHTCServiceData {
    count: number;
    data: GamitHTCData[];
    total_count: number;
}

export interface NetworkServiceData {
    count: number;
    total_count: number;
    data: NetworkData[];
    statusCode: number;
}

export interface CountriesServiceData {
    count: number;
    total_count: number;
    data: CountriesData[];
    statusCode: number;
}

export interface RinexServiceData {
    count: number;
    total_count: number;
    data: RinexData[];
    statusCode: number;
}

export interface LoginServiceData {
    refresh: string;
    access: string;
}

export interface UsersServiceData {
    count: number;
    total_count: number;
    data: UsersData[];
}

export interface RolesServiceData {
    count: number;
    total_count: number;
    data: Role[];
}

export interface ClusterServiceData {
    count: number;
    total_count: number;
    data: EndpointCluster[];
}

export interface FrontPagesServiceData {
    count: number;
    total_count: number;
    data: FrontPagesData[];
}

export interface RolesServiceData {}

export interface UsersData {
    address: string;
    email: string;
    first_name: string;
    id: number | null;
    is_active: boolean | null;
    last_name: string;
    phone: string;
    photo: string | null;
    role: { id: number | null; name: string };
    username: string;
    passsword?: string;
}

export interface ExtendedUsersData extends UsersData {
    statusCode: number;
}

export interface User {
    first_name: string;
    last_name: string;
    username: string;
    password: string;
    role: number | null;
    email?: string;
    phone?: string;
    address?: string;
    photo?: string | null;
    is_active?: boolean | null;
}

export interface Role {
    id: number;
    name: string;
    role_api: boolean;
    is_active: boolean;
    allow_all: boolean;
    endpoints_clusters: number[];
    pages: number[];
    statusCode: number;
}

export interface Cluster {
    id: number;
    name: string;
}

export interface EndpointCluster {
    [key: string]: [
        {
            id: number;
            resource: string;
            description: string;
            cluster_type: Cluster;
            endpoints: [number];
        },
    ];
}

export interface FrontPagesData {
    [key: string]: [
        {
            description: string;
            endpoint_clusters: [number];
            id: number;
            url: string;
        },
    ];
}
export interface NetworkData {
    api_id: number;
    network_code: string;
    network_name: string;
}

export interface CountriesData {
    id: number;
    name: string;
    three_digits_code: string;
    two_digits_code: string;
}

export interface RinexData {
    api_id: number;
    network_code: string;
    station_code: string;
    observation_year: number;
    observation_month: number;
    observation_day: number;
    observation_doy: number;
    observation_f_year: number;
    observation_s_time: string;
    observation_e_time: string;
    receiver_type: string;
    receiver_serial: string;
    receiver_fw: string;
    antenna_type: string;
    antenna_serial: string;
    antenna_dome: string;
    filename: string;
    interval: number;
    antenna_offset: number;
    completion: number;
}

export interface StationData {
    api_id?: number;
    network_code: string;
    station_code: string;
    station_name: string;
    date_start: number;
    date_end: number;
    auto_x: number;
    auto_y: number;
    auto_z: number;
    harpos_coeff_otl: string;
    lat: number;
    lon: number;
    height: number;
    max_dist: number;
    dome: string;
    country_code: string;
    marker: number;
}

export interface StationInfoData {
    antenna_code: string;
    antenna_east: number;
    antenna_height: number;
    antenna_north: number;
    antenna_serial: string;
    api_id: number;
    comments: null | string;
    date_end: string;
    date_start: string;
    height_code: string;
    network_code: string;
    radome_code: string;
    receiver_code: string;
    receiver_firmware: string;
    receiver_serial: string;
    receiver_vers: string;
    station_code: string;
}

export interface ReceiversData {
    api_id: number;
    receiver_code: string;
    receiver_description: string | null;
}

export interface AntennaData {
    api_id: number;
    antenna_code: string;
    antenna_description: string | null;
}

export interface GamitHTCData {
    antenna_code: string;
    api_id: number;
    h_offset: number;
    height_code: string;
    v_offset: number;
}