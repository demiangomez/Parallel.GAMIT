--
-- PostgreSQL database dump
--

-- Dumped from database version 9.6.1
-- Dumped by pg_dump version 9.6.1

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


SET search_path = public, pg_catalog;

--
-- Name: update_station_timespan(character varying, character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION update_station_timespan("NetworkCode" character varying, "StationCode" character varying) RETURNS void
    LANGUAGE sql
    AS $_$
update stations set 
"DateStart" = 
    (SELECT MIN("ObservationFYear") as MINN 
     FROM rinex WHERE "NetworkCode" = $1 AND
     "StationCode" = $2),
"DateEnd" = 
    (SELECT MAX("ObservationFYear") as MAXX 
     FROM rinex WHERE "NetworkCode" = $1 AND
     "StationCode" = $2)
WHERE "NetworkCode" = $1 AND "StationCode" = $2
$_$;


ALTER FUNCTION public.update_station_timespan("NetworkCode" character varying, "StationCode" character varying) OWNER TO postgres;

--
-- Name: update_timespan_trigg(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION update_timespan_trigg() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    update stations set 
"DateStart" = 
    (SELECT MIN("ObservationFYear") as MINN 
     FROM rinex 
     WHERE "NetworkCode" = new."NetworkCode" AND
           "StationCode" = new."StationCode"),
"DateEnd" = 
    (SELECT MAX("ObservationFYear") as MAXX 
     FROM rinex 
     WHERE "NetworkCode" = new."NetworkCode" AND
           "StationCode" = new."StationCode")
WHERE "NetworkCode" = new."NetworkCode" 
  AND "StationCode" = new."StationCode";

           RETURN new;
END;
$$;


ALTER FUNCTION public.update_timespan_trigg() OWNER TO postgres;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: antennas; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE antennas (
    "AntennaCode" character varying(22) NOT NULL,
    "AntennaDescription" character varying
);


ALTER TABLE antennas OWNER TO postgres;

--
-- Name: apr_coords; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE apr_coords (
    "NetworkCode" character varying(3) NOT NULL,
    "StationCode" character varying(4) NOT NULL,
    "Year" timestamp without time zone NOT NULL,
    "DOY" timestamp without time zone NOT NULL,
    "FYear" numeric,
    x numeric,
    y numeric,
    z numeric,
    sn numeric,
    se numeric,
    su numeric,
    "ReferenceFrame" character varying(20)
);


ALTER TABLE apr_coords OWNER TO postgres;

--
-- Name: earthquakes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE earthquakes (
    date timestamp without time zone NOT NULL,
    lat numeric NOT NULL,
    lon numeric NOT NULL,
    depth numeric,
    mag numeric
);


ALTER TABLE earthquakes OWNER TO postgres;

--
-- Name: events; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE events (
    event_id integer NOT NULL,
    "EventDate" timestamp without time zone DEFAULT now(),
    "EventType" character varying(6),
    "EventDescription" text
);


ALTER TABLE events OWNER TO postgres;

--
-- Name: events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE events_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE events_event_id_seq OWNER TO postgres;

--
-- Name: events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE events_event_id_seq OWNED BY events.event_id;


--
-- Name: gamit_soln; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE gamit_soln (
    "NetworkCode" character varying(3) NOT NULL,
    "StationCode" character varying(4) NOT NULL,
    "Project" character varying(20) NOT NULL,
    "Year" numeric NOT NULL,
    "DOY" numeric NOT NULL,
    "FYear" numeric,
    "X" numeric,
    "Y" numeric,
    "Z" numeric,
    sigmax numeric,
    sigmay numeric,
    sigmaz numeric,
    "VarianceFactor" numeric,
    sigmaxy numeric,
    sigmayz numeric,
    sigmaxz numeric
);


ALTER TABLE gamit_soln OWNER TO postgres;

--
-- Name: keys; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE keys (
    "KeyCode" character varying(7) NOT NULL,
    "TotalChars" integer,
    rinex_col_out character varying,
    rinex_col_in character varying(60),
    isnumeric bit(1)
);


ALTER TABLE keys OWNER TO postgres;

--
-- Name: locks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE locks (
    filename text NOT NULL,
    "NetworkCode" character varying(3),
    "StationCode" character varying(4)
);


ALTER TABLE locks OWNER TO postgres;

--
-- Name: networks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE networks (
    "NetworkCode" character varying NOT NULL,
    "NetworkName" character varying
);


ALTER TABLE networks OWNER TO postgres;

--
-- Name: ppp_soln; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE ppp_soln (
    "NetworkCode" character varying NOT NULL,
    "StationCode" character varying NOT NULL,
    "X" numeric(12,4),
    "Y" numeric(12,4),
    "Z" numeric(12,4),
    "Year" numeric NOT NULL,
    "DOY" numeric NOT NULL,
    "ReferenceFrame" character varying(20) NOT NULL,
    sigmax numeric,
    sigmay numeric,
    sigmaz numeric,
    sigmaxy numeric,
    sigmaxz numeric,
    sigmayz numeric
);


ALTER TABLE ppp_soln OWNER TO postgres;

--
-- Name: ppp_soln_excl; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE ppp_soln_excl (
    "NetworkCode" character varying(3) NOT NULL,
    "StationCode" character varying(4) NOT NULL,
    "Year" numeric NOT NULL,
    "DOY" numeric NOT NULL
);


ALTER TABLE ppp_soln_excl OWNER TO postgres;

--
-- Name: receivers; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE receivers (
    "ReceiverCode" character varying(22) NOT NULL,
    "ReceiverDescription" character varying(22)
);


ALTER TABLE receivers OWNER TO postgres;

--
-- Name: rinex; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE rinex (
    "NetworkCode" character varying NOT NULL,
    "StationCode" character varying NOT NULL,
    "ObservationYear" numeric NOT NULL,
    "ObservationMonth" numeric NOT NULL,
    "ObservationDay" numeric NOT NULL,
    "ObservationDOY" numeric NOT NULL,
    "ObservationFYear" numeric NOT NULL,
    "ObservationSTime" timestamp without time zone,
    "ObservationETime" timestamp without time zone,
    "ReceiverType" character varying(20),
    "ReceiverSerial" character varying(20),
    "ReceiverFw" character varying(20),
    "AntennaType" character varying(20),
    "AntennaSerial" character varying(20),
    "AntennaDome" character varying(20),
    "Filename" character varying(20),
    "Interval" numeric,
    "AntennaOffset" numeric
);


ALTER TABLE rinex OWNER TO postgres;

--
-- Name: rinex_extra; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE rinex_extra (
    "NetworkCode" character varying NOT NULL,
    "StationCode" character varying NOT NULL,
    "ObservationYear" numeric NOT NULL,
    "ObservationMonth" numeric NOT NULL,
    "ObservationDay" numeric NOT NULL,
    "ObservationDOY" numeric NOT NULL,
    "ObservationFYear" numeric NOT NULL,
    "ObservationSTime" timestamp without time zone,
    "ObservationETime" timestamp without time zone,
    "ReceiverType" character varying(20),
    "ReceiverSerial" character varying(20),
    "ReceiverFw" character varying(20),
    "AntennaType" character varying(20),
    "AntennaSerial" character varying(20),
    "AntennaDome" character varying(20),
    "Filename" character varying NOT NULL,
    "Interval" numeric,
    "AntennaOffset" numeric
);


ALTER TABLE rinex_extra OWNER TO postgres;

--
-- Name: rinex_tank_struct; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE rinex_tank_struct (
    "Level" integer NOT NULL,
    "KeyCode" character varying(7)
);


ALTER TABLE rinex_tank_struct OWNER TO postgres;

--
-- Name: stationinfo; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE stationinfo (
    "NetworkCode" character varying(3) NOT NULL,
    "StationCode" character varying(4) NOT NULL,
    "ReceiverCode" character varying(22) NOT NULL,
    "ReceiverSerial" character varying(22),
    "ReceiverFirmware" character varying(10),
    "AntennaCode" character varying(22) NOT NULL,
    "AntennaSerial" character varying(20),
    "AntennaHeight" numeric(6,4),
    "AntennaNorth" numeric(12,4),
    "AntennaEast" numeric(12,4),
    "HeightCode" character varying,
    "RadomeCode" character varying(7) NOT NULL,
    "DateStart" timestamp without time zone NOT NULL,
    "DateEnd" timestamp without time zone,
    "ReceiverVers" character varying(22)
);


ALTER TABLE stationinfo OWNER TO postgres;

--
-- Name: stations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE stations (
    "NetworkCode" character varying(3) NOT NULL,
    "StationCode" character varying(4) NOT NULL,
    "StationName" character varying(40),
    "DateStart" numeric(7,3),
    "DateEnd" numeric(7,3),
    auto_x numeric,
    auto_y numeric,
    auto_z numeric,
    "Harpos_coeff_otl" text,
    lat numeric,
    lon numeric,
    height numeric
);


ALTER TABLE stations OWNER TO postgres;

--
-- Name: events event_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY events ALTER COLUMN event_id SET DEFAULT nextval('events_event_id_seq'::regclass);


--
-- Name: antennas antennas_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY antennas
    ADD CONSTRAINT antennas_pkey PRIMARY KEY ("AntennaCode");


--
-- Name: apr_coords apr_coords_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY apr_coords
    ADD CONSTRAINT apr_coords_pkey PRIMARY KEY ("NetworkCode", "StationCode", "Year", "DOY");


--
-- Name: stationinfo date_chk; Type: CHECK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE stationinfo
    ADD CONSTRAINT date_chk CHECK (("DateEnd" > "DateStart")) NOT VALID;


--
-- Name: earthquakes earthquakes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY earthquakes
    ADD CONSTRAINT earthquakes_pkey PRIMARY KEY (date, lat, lon);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY events
    ADD CONSTRAINT events_pkey PRIMARY KEY (event_id);


--
-- Name: gamit_soln gamit_soln_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY gamit_soln
    ADD CONSTRAINT gamit_soln_pkey PRIMARY KEY ("NetworkCode", "StationCode", "Project", "Year", "DOY");


--
-- Name: keys keys_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY keys
    ADD CONSTRAINT keys_pkey PRIMARY KEY ("KeyCode");


--
-- Name: locks locks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY locks
    ADD CONSTRAINT locks_pkey PRIMARY KEY (filename);


--
-- Name: networks networks_NetworkCode_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY networks
    ADD CONSTRAINT "networks_NetworkCode_pkey" PRIMARY KEY ("NetworkCode");


--
-- Name: ppp_soln_excl ppp_soln_excl_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY ppp_soln_excl
    ADD CONSTRAINT ppp_soln_excl_pkey PRIMARY KEY ("NetworkCode", "StationCode", "Year", "DOY");


--
-- Name: ppp_soln ppp_soln_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY ppp_soln
    ADD CONSTRAINT ppp_soln_pkey PRIMARY KEY ("NetworkCode", "StationCode", "Year", "DOY", "ReferenceFrame");


--
-- Name: receivers receivers_ReceiverCode_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY receivers
    ADD CONSTRAINT "receivers_ReceiverCode_pkey" PRIMARY KEY ("ReceiverCode");


--
-- Name: rinex_extra rinex_extra_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY rinex_extra
    ADD CONSTRAINT rinex_extra_pkey PRIMARY KEY ("NetworkCode", "StationCode", "ObservationYear", "ObservationMonth", "ObservationDay", "Filename");


--
-- Name: rinex rinex_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY rinex
    ADD CONSTRAINT rinex_pkey PRIMARY KEY ("NetworkCode", "StationCode", "ObservationYear", "ObservationDOY");


--
-- Name: rinex_tank_struct rinex_tank_struct_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY rinex_tank_struct
    ADD CONSTRAINT rinex_tank_struct_pkey PRIMARY KEY ("Level");


--
-- Name: stationinfo stationinfo_NetworkCode_StationCode_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY stationinfo
    ADD CONSTRAINT "stationinfo_NetworkCode_StationCode_pkey" PRIMARY KEY ("NetworkCode", "StationCode", "DateStart");


--
-- Name: stations stations_NetworkCode_StationCode_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY stations
    ADD CONSTRAINT "stations_NetworkCode_StationCode_pkey" PRIMARY KEY ("NetworkCode", "StationCode");


--
-- Name: stations_NetworkCode_StationCode_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX "stations_NetworkCode_StationCode_idx" ON stations USING btree ("NetworkCode", "StationCode");


--
-- Name: rinex update_stations; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_stations AFTER INSERT ON rinex FOR EACH ROW EXECUTE PROCEDURE update_timespan_trigg();


--
-- Name: stations NetworkCode; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY stations
    ADD CONSTRAINT "NetworkCode" FOREIGN KEY ("NetworkCode") REFERENCES networks("NetworkCode") MATCH FULL ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: apr_coords apr_coords_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY apr_coords
    ADD CONSTRAINT "apr_coords_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES stations("NetworkCode", "StationCode");


--
-- Name: gamit_soln gamit_soln_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY gamit_soln
    ADD CONSTRAINT "gamit_soln_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: gamit_soln gamit_soln_NetworkCode_fkey1; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY gamit_soln
    ADD CONSTRAINT "gamit_soln_NetworkCode_fkey1" FOREIGN KEY ("NetworkCode", "StationCode", "Year", "DOY") REFERENCES rinex("NetworkCode", "StationCode", "ObservationYear", "ObservationDOY") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: locks locks_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY locks
    ADD CONSTRAINT "locks_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: ppp_soln ppp_soln_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY ppp_soln
    ADD CONSTRAINT "ppp_soln_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode", "Year", "DOY") REFERENCES rinex("NetworkCode", "StationCode", "ObservationYear", "ObservationDOY") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: ppp_soln ppp_soln_NetworkName_StationCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY ppp_soln
    ADD CONSTRAINT "ppp_soln_NetworkName_StationCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: ppp_soln_excl ppp_soln_excl_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY ppp_soln_excl
    ADD CONSTRAINT "ppp_soln_excl_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: rinex rinex_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY rinex
    ADD CONSTRAINT "rinex_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: rinex_extra rinex_extra_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY rinex_extra
    ADD CONSTRAINT "rinex_extra_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: rinex_tank_struct rinex_tank_struct_key_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY rinex_tank_struct
    ADD CONSTRAINT rinex_tank_struct_key_fkey FOREIGN KEY ("KeyCode") REFERENCES keys("KeyCode");


--
-- Name: stationinfo stationinfo_AntennaCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY stationinfo
    ADD CONSTRAINT "stationinfo_AntennaCode_fkey" FOREIGN KEY ("AntennaCode") REFERENCES antennas("AntennaCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: stationinfo stationinfo_NetworkCode_StationCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY stationinfo
    ADD CONSTRAINT "stationinfo_NetworkCode_StationCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: stationinfo stationinfo_ReceiverCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY stationinfo
    ADD CONSTRAINT "stationinfo_ReceiverCode_fkey" FOREIGN KEY ("ReceiverCode") REFERENCES receivers("ReceiverCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--

