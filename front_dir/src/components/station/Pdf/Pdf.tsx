// prettier-ignore
import {
    Page,
    Text,
    View,
    Document,
    StyleSheet,
    Svg,
    Line,
    Font,
    Image,
} from "@react-pdf/renderer";

import { adjustToLocalTimezone, decimalToDMS, formattedDates } from "@utils";

import {
    MonumentTypes,
    People,
    RinexData,
    StationData,
    StationImagesData,
    StationInfoData,
    StationMetadataServiceData,
    StationVisitsData,
    StationVisitsFilesData,
} from "@types";

interface Props {
    stationInfo: StationInfoData | undefined;
    monuments: MonumentTypes | undefined;
    people: ((People & { role: string }) | undefined)[];
    station: StationData | undefined;
    stationMeta: StationMetadataServiceData | undefined;
    images: StationImagesData[] | undefined;
    firstRinex: RinexData | undefined;
    lastRinex: RinexData | undefined;
    visits: StationVisitsData[] | undefined;
    visitFiles: StationVisitsFilesData[] | undefined;
    visitGnssFiles: StationVisitsFilesData[] | undefined;
    visitImages: StationVisitsFilesData[] | undefined;
    stationLocationScreen: string;
    stationLocationDetailScreen: string;
}

const Pdf = ({
    stationInfo,
    monuments,
    people,
    station,
    stationMeta,
    lastRinex,
    firstRinex,
    images,
    visits,
    visitFiles,
    visitGnssFiles,
    visitImages,
    stationLocationScreen,
    stationLocationDetailScreen,
}: Props) => {
    Font.register({
        family: "Lora",
        fonts: [
            {
                src: "https://fonts.gstatic.com/s/lora/v35/0QI6MX1D_JOuGQbT0gvTJPa787weuyJGmKxemMeZ.ttf",
            },
            {
                src: "https://fonts.gstatic.com/s/lora/v35/0QI6MX1D_JOuGQbT0gvTJPa787zAvCJGmKxemMeZ.ttf",
                fontWeight: 600,
            },
            {
                src: "https://fonts.gstatic.com/s/lora/v35/0QI6MX1D_JOuGQbT0gvTJPa787z5vCJGmKxemMeZ.ttf",
                fontWeight: 700,
            },
        ],
    });

    const styles = StyleSheet.create({
        locationScreen: {
            width: "100%",
            height: 230,
            uri: `${stationLocationScreen}`,
        },
        locationDetailScreen: {
            width: "100%",
            height: 250,
            uri: `${stationLocationDetailScreen}`,
        },
        page: {
            flexDirection: "row",
            // backgroundColor: "#E4E4E4",
            backgroundColor: "#FFFFFF",
            fontFamily: "Lora",
            paddingTop: 35,
            paddingHorizontal: 35,
        },
        section: {
            display: "flex",
            width: "100%",
            flexDirection: "column",
        },
        viewHeader: {
            display: "flex",
            flexDirection: "row",
            justifyContent: "space-between",
            backgroundColor: "#d9d9d9",
            padding: 10,
            width: "100%",
        },
        textBold: {
            fontSize: 24,
            color: "#000000",
            fontWeight: "ultrabold",
        },
        textSemibold: {
            fontSize: 20,
            textAlign: "justify",
            color: "#000000",
            fontWeight: "semibold",
        },
        headersTitle: {
            fontSize: 16,
            color: "#000000",
            fontWeight: "semibold",
        },
    });

    return (
        <Document>
            <Page size="A4" style={styles.page}>
                <View style={{ display: "flex", width: "100%" }}>
                    <View style={styles.section} fixed>
                        <View
                            style={{
                                display: "flex",
                                flexDirection: "row",
                                justifyContent: "space-between",
                                width: "100%",
                            }}
                        >
                            <Text style={styles.textBold}>
                                GNSS Station Report
                            </Text>
                            <Text>
                                Printed on{" "}
                                {formattedDates(new Date())?.split(",")[0]}{" "}
                            </Text>
                        </View>

                        <Svg height="3" style={{ marginTop: "10px" }}>
                            <Line
                                x1="0"
                                y1="0"
                                x2="555"
                                y2="0"
                                strokeWidth={2}
                                stroke="rgb(0,0,0)"
                            />
                        </Svg>
                        <Svg height="3">
                            <Line
                                x1="0"
                                y1="0"
                                x2="555"
                                y2="0"
                                strokeWidth={1}
                                stroke="rgb(0,0,0)"
                            />
                        </Svg>
                        <Svg height="3">
                            <Line
                                x1="0"
                                y1="0"
                                x2="555"
                                y2="0"
                                strokeWidth={2}
                                stroke="rgb(0,0,0)"
                            />
                        </Svg>
                    </View>

                    <View style={styles.viewHeader}>
                        <Text style={styles.headersTitle}>Station Name</Text>
                        <Text style={styles.headersTitle}>
                            Geodetic coordinates
                        </Text>
                        <Text style={styles.headersTitle}>
                            Geocentric Coordinates
                        </Text>
                    </View>
                    <View
                        style={{
                            display: "flex",
                            flexDirection: "row",
                            width: "100%",
                            margin: 10,
                        }}
                    >
                        <View style={{ width: "24%", fontSize: 12 }}>
                            <View
                                style={{
                                    display: "flex",
                                    flexDirection: "row",
                                }}
                            >
                                <Text>Network code: </Text>
                                <Text style={{ fontWeight: "bold" }}>
                                    {station?.network_code.toUpperCase()}
                                </Text>
                            </View>
                            <View
                                style={{
                                    display: "flex",
                                    flexDirection: "row",
                                }}
                            >
                                <Text>Station code: </Text>
                                <Text style={{ fontWeight: "bold" }}>
                                    {station?.station_code.toUpperCase()}
                                </Text>
                            </View>
                            <View
                                style={{
                                    display: "flex",
                                    flexDirection: "row",
                                }}
                            >
                                <Text>Country code: </Text>
                                <Text style={{ fontWeight: "bold" }}>
                                    {station?.country_code.toUpperCase()}
                                </Text>
                            </View>
                        </View>
                        <View style={{ width: "48%", fontSize: 12 }}>
                            <Text>
                                <Text>Latitude:</Text>
                                <Text>
                                    {" "}
                                    {decimalToDMS(
                                        Number(station?.lat.toFixed(8)),
                                        true,
                                    ) +
                                        " " +
                                        "(" +
                                        station?.lat.toFixed(8) +
                                        ")"}
                                </Text>
                            </Text>
                            <Text>
                                <Text>Longitude:</Text>
                                <Text>
                                    {" "}
                                    {decimalToDMS(
                                        Number(station?.lon.toFixed(8)),
                                        false,
                                    ) +
                                        " " +
                                        "(" +
                                        station?.lon.toFixed(8) +
                                        ")"}
                                </Text>
                            </Text>
                            <Text>
                                <Text>Height:</Text>
                                <Text> {Number(station?.height) + " m"}</Text>
                            </Text>
                        </View>
                        <View style={{ width: "28%", fontSize: 12 }}>
                            <Text>
                                <Text>X: </Text>
                                <Text>{station?.auto_x + " m"}</Text>
                            </Text>
                            <Text>
                                <Text>Y: </Text>
                                <Text>{station?.auto_y + " m"}</Text>
                            </Text>
                            <Text>
                                <Text>Z: </Text>
                                <Text>{station?.auto_z + " m"}</Text>
                            </Text>
                        </View>
                    </View>

                    <View>
                        <Text
                            style={{
                                fontWeight: "bold",
                                marginHorizontal: "10",
                            }}
                        >
                            Location map
                        </Text>
                        <View style={styles.viewHeader}>
                            <Text
                                style={[
                                    styles.headersTitle,
                                    { textAlign: "center", width: "100%" },
                                ]}
                            >
                                General
                            </Text>
                        </View>

                        {/* Imagen General */}
                        <Image
                            src={{
                                uri: stationLocationScreen ?? "",
                                method: "GET",
                                headers: {},
                                body: "",
                            }}
                            style={{
                                // height: 230,
                                // width: "100%",
                                width: "100%",
                                height: "auto",
                                objectFit: "scale-down",
                                marginVertical: 10,
                            }}
                        />

                        <View
                            style={[styles.viewHeader, { marginTop: 40 }]}
                            break
                        >
                            <Text
                                style={[
                                    styles.headersTitle,
                                    {
                                        textAlign: "center",
                                        width: "100%",
                                    },
                                ]}
                            >
                                Detail
                            </Text>
                        </View>

                        {/* Imagen General */}
                        <Image
                            src={{
                                uri: stationLocationDetailScreen ?? "",
                                method: "GET",
                                headers: {},
                                body: "",
                            }}
                            style={{
                                marginVertical: 10,
                                width: "100%",
                                height: "auto",

                                objectFit: "scale-down",
                            }}
                        />
                    </View>

                    <View style={[styles.section, { fontSize: 14 }]} break>
                        <Text style={{ fontWeight: "bold", fontSize: 20 }}>
                            Current Instrument
                        </Text>
                        <View style={{ marginTop: 5 }}>
                            <Text>
                                Receiver Type:{" "}
                                {stationInfo?.receiver_code !== ""
                                    ? stationInfo?.receiver_code
                                    : "N/A"}
                            </Text>
                            <Text>
                                Receiver Serial Number:{" "}
                                {stationInfo?.receiver_serial !== ""
                                    ? stationInfo?.receiver_serial
                                    : "N/A"}
                            </Text>
                            <Text>
                                Receiver Firmware:{" "}
                                {stationInfo?.receiver_firmware !== ""
                                    ? stationInfo?.receiver_firmware
                                    : "N/A"}
                            </Text>
                            <Text>
                                Receiver Version:{" "}
                                {stationInfo?.receiver_vers !== ""
                                    ? stationInfo?.receiver_vers
                                    : "N/A"}
                            </Text>
                        </View>

                        <View style={{ marginTop: 10 }}>
                            <Text>
                                Antenna Type:{" "}
                                {stationInfo?.antenna_code !== ""
                                    ? stationInfo?.antenna_code
                                    : "N/A"}
                            </Text>

                            <Text>
                                Antenna Serial Number:{" "}
                                {stationInfo?.antenna_serial !== ""
                                    ? stationInfo?.antenna_serial
                                    : "N/A"}
                            </Text>
                        </View>
                        <View style={{ marginTop: 10 }}>
                            <Text>
                                Height Code:{" "}
                                {stationInfo?.height_code !== ""
                                    ? stationInfo?.height_code
                                    : "N/A"}
                            </Text>

                            <Text>
                                Radome Code:{" "}
                                {stationInfo?.radome_code !== ""
                                    ? stationInfo?.radome_code
                                    : "N/A"}
                            </Text>
                        </View>
                    </View>

                    <View style={styles.section} break>
                        <Text
                            style={{
                                fontWeight: "bold",
                                fontSize: 20,
                                marginTop: 10,
                            }}
                        >
                            Site pictures
                        </Text>
                        {images && images.length > 0 ? (
                            images?.map((img, idx) => (
                                <Image
                                    key={img.id + String(idx)}
                                    style={{
                                        // width: 400,
                                        // height: 300,
                                        width: "auto",
                                        height: 300,
                                        marginVertical: 10,
                                        objectFit: "scale-down",
                                    }}
                                    src={{
                                        uri: `${img.actual_image}`,
                                        method: "GET",
                                        headers: {},
                                        body: "",
                                    }}
                                />
                            ))
                        ) : (
                            <Text style={{ marginVertical: 10, fontSize: 12 }}>
                                No images found
                            </Text>
                        )}
                    </View>

                    <View style={styles.section} break={true}>
                        <Text style={{ fontWeight: "bold", fontSize: 20 }}>
                            Relevant metadata
                        </Text>
                        <View style={styles.viewHeader}>
                            <Text style={styles.headersTitle}>General</Text>
                            <Text style={styles.headersTitle}>
                                Contact information
                            </Text>
                        </View>
                    </View>

                    <View
                        style={{
                            display: "flex",
                            flexDirection: "row",
                            width: "100%",
                            marginTop: 10,
                        }}
                    >
                        <View
                            style={{
                                fontSize: 14,
                                marginRight: 10,
                                lineHeight: 1.5,
                            }}
                        >
                            <View
                                style={{
                                    flexDirection: "row",
                                    flexWrap: "wrap",
                                }}
                            >
                                <Text>Station type: </Text>
                                <Text style={{ fontWeight: "bold" }}>
                                    {stationMeta?.station_type_name ?? "N/A"}
                                </Text>
                            </View>
                            <View
                                style={{
                                    flexDirection: "row",
                                    flexWrap: "wrap",
                                }}
                            >
                                <Text>Monument: </Text>
                                <Text style={{ fontWeight: "bold" }}>
                                    {monuments?.name ?? "N/A"}
                                </Text>
                            </View>
                            <View
                                style={{
                                    flexDirection: "row",
                                    flexWrap: "wrap",
                                }}
                            >
                                <Text>Status: </Text>
                                <Text style={{ fontWeight: "bold" }}>
                                    {stationMeta?.station_status_name ?? "N/A"}
                                </Text>
                            </View>
                            <View
                                style={{
                                    display: "flex",
                                    flexDirection: "column",
                                }}
                            >
                                <View
                                    style={{
                                        flexDirection: "row",
                                        flexWrap: "wrap",
                                    }}
                                >
                                    <Text>Communications: </Text>
                                    <Text style={{ fontWeight: "bold" }}>
                                        {stationMeta?.has_communications
                                            ? "Yes"
                                            : "No"}
                                    </Text>
                                </View>
                                <Text style={{ marginHorizontal: 10 }}>
                                    {stationMeta?.communications_description}
                                </Text>
                            </View>
                            <View
                                style={{
                                    display: "flex",
                                    flexDirection: "column",
                                }}
                            >
                                <View
                                    style={{
                                        flexDirection: "row",
                                        flexWrap: "wrap",
                                    }}
                                >
                                    <Text>Battery: </Text>
                                    <Text style={{ fontWeight: "bold" }}>
                                        {stationMeta?.has_battery
                                            ? "Yes"
                                            : "No"}
                                    </Text>
                                </View>
                                <Text style={{ marginHorizontal: 10 }}>
                                    {stationMeta?.battery_description}
                                </Text>
                            </View>
                            <View
                                style={{
                                    flexDirection: "row",
                                    flexWrap: "wrap",
                                }}
                            >
                                <Text>First RINEX: </Text>
                                <Text style={{ fontWeight: "bold" }}>
                                    {firstRinex
                                        ? (formattedDates(
                                              new Date(
                                                  firstRinex?.observation_s_time,
                                              ),
                                          ) ?? "N/A")
                                        : "N/A"}
                                </Text>
                            </View>
                            <View
                                style={{
                                    flexDirection: "row",
                                    flexWrap: "wrap",
                                }}
                            >
                                <Text>Last RINEX: </Text>
                                <Text style={{ fontWeight: "bold" }}>
                                    {lastRinex
                                        ? (formattedDates(
                                              new Date(
                                                  lastRinex?.observation_s_time,
                                              ),
                                          ) ?? "N/A")
                                        : "N/A"}
                                </Text>
                            </View>
                        </View>
                        <View
                            style={{
                                width: "50%",
                                fontSize: 14,
                            }}
                        >
                            {people && people.length > 0 ? (
                                people?.map((person, idx) => {
                                    return (
                                        <View
                                            key={person?.id + String(idx)}
                                            style={{
                                                display: "flex",
                                                flexDirection: "column",
                                            }}
                                        >
                                            <View
                                                style={{
                                                    flexDirection: "row",
                                                    flexWrap: "wrap",
                                                }}
                                            >
                                                <Text>
                                                    {" "}
                                                    {person?.first_name}{" "}
                                                    {person?.last_name}:
                                                </Text>
                                                <Text>
                                                    {" "}
                                                    {person?.role ?? ""}
                                                </Text>
                                            </View>
                                            <Text> {person?.email}</Text>
                                            <Text> {person?.phone}</Text>
                                        </View>
                                    );
                                })
                            ) : (
                                <Text>No people found</Text>
                            )}
                        </View>
                    </View>

                    <View
                        style={{
                            display: "flex",
                            flexDirection: "column",
                            width: "100%",
                        }}
                    >
                        <Text style={{ fontWeight: "bold", fontSize: 20 }}>
                            Comments
                        </Text>
                        <Text style={{ fontSize: 12 }}>
                            {stationMeta?.comments !== ""
                                ? stationMeta?.comments
                                : "None"}
                        </Text>
                    </View>

                    <View style={styles.section} break={true}>
                        <Text
                            style={{
                                fontWeight: "bold",
                                fontSize: 20,
                                marginTop: 10,
                            }}
                        >
                            List of visits
                        </Text>
                        <Svg height="5">
                            <Line
                                x1="00"
                                y1="0"
                                x2="590"
                                y2="0"
                                strokeWidth={1}
                                stroke="rgb(0,0,0)"
                            />
                        </Svg>
                        <View
                            style={{
                                display: "flex",
                                flexDirection: "column",
                                width: "100%",
                            }}
                        >
                            {visits && visits.length > 0 ? (
                                visits?.map((v: StationVisitsData, idx) => {
                                    const options: Intl.DateTimeFormatOptions =
                                        {
                                            month: "short",
                                            day: "2-digit",
                                            year: "numeric",
                                        };

                                    const date = adjustToLocalTimezone(
                                        v.date,
                                    ).toLocaleDateString("en-US", options);

                                    const gnssFiles = visitGnssFiles?.filter(
                                        (gf) => gf.visit === v.id,
                                    );

                                    const files = visitFiles?.filter(
                                        (f) => f.visit === v.id,
                                    );
                                    v.log_sheet_filename !== ""
                                        ? files?.push({
                                              visit: v.id,
                                              description: "log_sheet",
                                              name: "",
                                              id: Math.random(),
                                              actual_image:
                                                  v?.log_sheet_actual_file ??
                                                  "",
                                              filename:
                                                  v?.log_sheet_filename ?? "",
                                          })
                                        : null;

                                    v.navigation_filename !== ""
                                        ? files?.push({
                                              visit: v.id,
                                              description: "navigation_file",
                                              name: "",
                                              id: Math.random(),
                                              actual_image:
                                                  v?.navigation_actual_file ??
                                                  "",
                                              filename:
                                                  v?.navigation_filename ?? "",
                                          })
                                        : null;

                                    const images = visitImages?.filter(
                                        (vi) => vi.visit === v.id,
                                    );

                                    return (
                                        <View
                                            key={v.id + v.date}
                                            style={{
                                                display: "flex",
                                                flexDirection: "column",
                                                width: "100%",
                                            }}
                                            break={idx !== 0}
                                        >
                                            <View
                                                style={{
                                                    display: "flex",
                                                    flexDirection: "row",
                                                    width: "100%",
                                                    marginVertical: 10,
                                                }}
                                            >
                                                <Text
                                                    style={{
                                                        fontWeight: "bold",
                                                        fontSize: 16,
                                                    }}
                                                >
                                                    Visit on {date} -
                                                </Text>
                                                <Text
                                                    style={{
                                                        fontWeight: "bold",
                                                        fontSize: 16,
                                                    }}
                                                >
                                                    {" "}
                                                    Campaign:{" "}
                                                    {v?.campaign_name ?? "none"}
                                                </Text>
                                            </View>
                                            <View style={styles.viewHeader}>
                                                <Text
                                                    style={styles.headersTitle}
                                                >
                                                    People
                                                </Text>
                                                <Text
                                                    style={styles.headersTitle}
                                                >
                                                    List of observation files
                                                </Text>
                                                <Text
                                                    style={styles.headersTitle}
                                                >
                                                    List of attached files
                                                </Text>
                                            </View>
                                            <View
                                                style={{
                                                    display: "flex",
                                                    flexDirection: "row",
                                                    width: "100%",
                                                    margin: 10,
                                                }}
                                            >
                                                <View
                                                    style={{
                                                        width: "20%",
                                                        fontSize: 12,
                                                    }}
                                                >
                                                    {v.people &&
                                                    v.people.length > 0 ? (
                                                        v.people.map(
                                                            (p: {
                                                                id: string;
                                                                name: string;
                                                            }) => {
                                                                return (
                                                                    <View
                                                                        key={
                                                                            p.id +
                                                                            p.name
                                                                        }
                                                                        style={{
                                                                            display:
                                                                                "flex",
                                                                            flexDirection:
                                                                                "column",
                                                                        }}
                                                                    >
                                                                        <Text>
                                                                            {
                                                                                p.name
                                                                            }
                                                                        </Text>
                                                                    </View>
                                                                );
                                                            },
                                                        )
                                                    ) : (
                                                        <Text>
                                                            No people Found
                                                        </Text>
                                                    )}
                                                </View>
                                                <View
                                                    style={{
                                                        width: "40%",
                                                        fontSize: 12,
                                                        marginLeft: 5,
                                                    }}
                                                >
                                                    {gnssFiles &&
                                                    gnssFiles.length > 0 ? (
                                                        <>
                                                            {gnssFiles
                                                                .slice(0, 3)
                                                                .map(
                                                                    (
                                                                        f,
                                                                        idx,
                                                                    ) => (
                                                                        <View
                                                                            key={
                                                                                idx
                                                                            }
                                                                            style={{
                                                                                display:
                                                                                    "flex",
                                                                                flexDirection:
                                                                                    "column",
                                                                            }}
                                                                        >
                                                                            <Text>
                                                                                {
                                                                                    f.filename
                                                                                }
                                                                                {idx ===
                                                                                    2 &&
                                                                                    gnssFiles.length >
                                                                                        3 &&
                                                                                    " ..."}
                                                                            </Text>
                                                                        </View>
                                                                    ),
                                                                )}
                                                            {gnssFiles.length <=
                                                                3 &&
                                                                gnssFiles
                                                                    .slice(3)
                                                                    .map(
                                                                        (
                                                                            f,
                                                                            idx,
                                                                        ) => (
                                                                            <View
                                                                                key={
                                                                                    idx +
                                                                                    3
                                                                                }
                                                                                style={{
                                                                                    display:
                                                                                        "flex",
                                                                                    flexDirection:
                                                                                        "column",
                                                                                }}
                                                                            >
                                                                                <Text>
                                                                                    {
                                                                                        f.filename
                                                                                    }
                                                                                </Text>
                                                                            </View>
                                                                        ),
                                                                    )}
                                                        </>
                                                    ) : (
                                                        <Text>
                                                            No files Found
                                                        </Text>
                                                    )}
                                                </View>
                                                <View
                                                    style={{
                                                        width: "40%",
                                                        fontSize: 12,
                                                    }}
                                                >
                                                    {files &&
                                                    files.length > 0 ? (
                                                        <>
                                                            {files
                                                                .slice(0, 3)
                                                                .map(
                                                                    (
                                                                        f,
                                                                        idx,
                                                                    ) => (
                                                                        <View
                                                                            key={
                                                                                idx
                                                                            }
                                                                            style={{
                                                                                display:
                                                                                    "flex",
                                                                                flexDirection:
                                                                                    "column",
                                                                            }}
                                                                        >
                                                                            <Text>
                                                                                {
                                                                                    f.filename
                                                                                }
                                                                                {idx ===
                                                                                    2 &&
                                                                                    files.length >
                                                                                        3 &&
                                                                                    " ..."}
                                                                            </Text>
                                                                        </View>
                                                                    ),
                                                                )}
                                                        </>
                                                    ) : (
                                                        <Text>
                                                            No files Found
                                                        </Text>
                                                    )}
                                                </View>
                                            </View>
                                            <View
                                                style={{
                                                    display: "flex",
                                                    flexDirection: "column",
                                                    width: "100%",
                                                }}
                                            >
                                                <Text style={styles.textBold}>
                                                    Comments
                                                </Text>
                                                <Text style={{ fontSize: 12 }}>
                                                    {v?.comments !== ""
                                                        ? v?.comments
                                                        : "None"}
                                                </Text>
                                            </View>

                                            <View
                                                style={{
                                                    display: "flex",
                                                    flexDirection: "column",
                                                    width: "100%",
                                                    marginTop: 10,
                                                }}
                                            >
                                                <Text
                                                    style={[
                                                        styles.textBold,
                                                        { marginBottom: 10 },
                                                    ]}
                                                >
                                                    Visit pictures
                                                </Text>
                                                {images && images.length > 0 ? (
                                                    images?.map((img, idx) => {
                                                        return (
                                                            <Image
                                                                key={
                                                                    img.id +
                                                                    String(idx)
                                                                }
                                                                style={{
                                                                    width: "auto",
                                                                    height: 300,
                                                                    marginVertical: 15,
                                                                    objectFit:
                                                                        "scale-down",
                                                                }}
                                                                src={{
                                                                    uri: `${img.actual_image}`,
                                                                    method: "GET",
                                                                    headers: {
                                                                        "Cache-Control":
                                                                            "no-cache",
                                                                    },
                                                                    body: "",
                                                                }}
                                                            />
                                                        );
                                                    })
                                                ) : (
                                                    <Text
                                                        style={{
                                                            marginVertical: 10,
                                                            fontSize: 12,
                                                        }}
                                                    >
                                                        No images found
                                                    </Text>
                                                )}
                                            </View>

                                            <Svg height="5">
                                                <Line
                                                    x1="00"
                                                    y1="0"
                                                    x2="590"
                                                    y2="0"
                                                    strokeWidth={1}
                                                    stroke="rgb(0,0,0)"
                                                />
                                            </Svg>
                                        </View>
                                    );
                                })
                            ) : (
                                <Text
                                    style={{ marginVertical: 10, fontSize: 12 }}
                                >
                                    No visits found
                                </Text>
                            )}
                        </View>
                    </View>
                </View>
                <Text
                    fixed
                    style={{
                        position: "absolute",
                        fontSize: 12,
                        bottom: 30,
                        left: 0,
                        right: 0,
                        textAlign: "center",
                        color: "grey",
                    }}
                >
                    {station?.network_code.toUpperCase()}.
                    {station?.station_code.toUpperCase()} (
                    {station?.country_code})
                </Text>
            </Page>
        </Document>
    );
};

export default Pdf;
