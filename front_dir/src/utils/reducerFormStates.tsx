export const STATION_INFO_STATE = {
    api_id: "",
    network_code: "",
    station_code: "",
    receiver_code: "",
    receiver_serial: "",
    receiver_firmware: "",
    antenna_code: "",
    antenna_serial: "",
    antenna_height: "",
    antenna_north: "",
    antenna_east: "",
    height_code: "",
    radome_code: "",
    date_start: "",
    date_end: "",
    receiver_vers: "",
    comments: "",
};

type UserState = {
    id: null | number;
    username: string;
    password: string;
    role: {
        id: null | number;
        name: string;
    };
    is_active: null | boolean;
    first_name: string;
    last_name: string;
    email: string;
    phone: string;
    address: string;
    photo: string;
    [key: string]: any; // Añade esta línea
};

export const USERS_STATE: UserState = {
    id: null,
    username: "",
    password: "",
    role: {
        id: null,
        name: "",
    },
    is_active: null,
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    address: "",
    photo: "",
};

export const VISIT_STATE = {
    station: "",
    date: "",
    log_sheet_file: "",
    navigation_file: "",
    campaign: "",
    people: "",
    comments: "",
};

export const CAMPAIGN_STATE = {
    name: "",
    start_date: "",
    end_date: "",
    default_people: [] as string[],
};

export const SOURCES_STATIONS_STATE = {
    network_code: "",
    station_code: "",
    try_order: "",
    path: "",
    format: "",
    server_id: "",
}

export const SOURCES_SERVERS_STATE = {
    server_id: "",
    format: "",
    fqdn: "",
    password: "",
    path: "",
    protocol: "",
    username: ""
}

export const SOURCES_FORMATS_STATE = {
    format: "",
    api_id: "",
}

export const METADATA_STATE = {
    stationMeta: {
        station_code: "",
        network_code: "",
        dome: "",
        max_dist: "",
    },
    station: {
        lat: "",
        lon: "",
        height: "",
        auto_x: "",
        auto_y: "",
        auto_z: "",
    },
}

export const EVENTS_FILTERS_STATE = {
    description: "",
    doy: "",
    event_date_since: "",
    event_date_until: "",
    event_type: "",
    module: "",
    network_code: "",
    node: "",
    stack: "",
    station_code: "",
    year: "",
};

export const RINEX_FILTERS_STATE = {
    antenna_dome: "",
    antenna_offset: "",
    antenna_serial: "",
    antenna_type: "",
    completion: "",
    interval: "",
    day: "",
    doy: "",
    e_time: "",
    f_year: "",
    month: "",
    s_time: "",
    year: "",
    receiver_fw: "",
    receiver_serial: "",
    receiver_type: "",
};

export const SERIES_FILTERS_STATE = {
    solution: "PPP",
    stack: "",
    date_start: "",
    date_end: "",
    residuals: false,
    missing_data: false,
    plot_outliers: false,
    plot_auto_jumps: false,
    no_model: false,
    remove_jumps: false,
    remove_polynomial: false,
};

export const SERIES_JUMP_DATA = {
    Year: "",
    DOY: "",
    action: "",
    jump_type: "",
    relaxation: [],
}

export const SERIES_POLYNOMIAL_DATA = {
    DOY: "",
    Year: "",
    terms: "",
}

export const SERIES_PERIODIC_DATA = {
    frequence: []
}