--
-- PostgreSQL database dump
--

-- Dumped from database version 16.4
-- Dumped by pg_dump version 17.2 (Ubuntu 17.2-1.pgdg22.04+1)

-- Started on 2024-12-06 13:37:01 EST

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 5 (class 2615 OID 2200)
-- Name: public; Type: SCHEMA; Schema: -; Owner: postgres
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO postgres;

--
-- TOC entry 368 (class 1255 OID 571419)
-- Name: delete_rows_referencing_stations(); Type: FUNCTION; Schema: public; Owner: gnss_data_osu
--

CREATE FUNCTION public.delete_rows_referencing_stations() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE
	    deleted_visit_id INTEGER;
    BEGIN
    	    -- delete related rows from api tables
        DELETE FROM api_stationmetagaps WHERE station_meta_id IN (SELECT id FROM api_stationmeta WHERE station_id = OLD.api_id);
	    DELETE FROM api_stationmeta WHERE station_id = OLD.api_id; 
	    DELETE FROM api_rolepersonstation WHERE station_id = OLD.api_id;
	    DELETE FROM api_stationimages WHERE station_id = OLD.api_id;
	    DELETE FROM api_stationattachedfiles WHERE station_id = OLD.api_id;
	    
	    -- delete visits and other related rows (also from api tables)
	    DELETE FROM api_visits WHERE station_id = OLD.api_id RETURNING id INTO deleted_visit_id;
	    DELETE FROM api_visitimages WHERE visit_id = deleted_visit_id;
	    DELETE FROM api_visitattachedfiles WHERE visit_id = deleted_visit_id;
	    DELETE FROM api_visitgnssdatafiles WHERE visit_id = deleted_visit_id;
	    DELETE FROM api_visits_people WHERE visits_id = deleted_visit_id;
	    
	    -- delete from stationinfo
	    DELETE FROM stationinfo WHERE "NetworkCode" = OLD."NetworkCode" and "StationCode" = OLD."StationCode";
	    
	    -- rinex rows must not be deleted
	    
	    RETURN OLD;
    END;
    $$;


ALTER FUNCTION public.delete_rows_referencing_stations() OWNER TO gnss_data_osu;

--
-- TOC entry 348 (class 1255 OID 16587)
-- Name: ecef2neu(numeric, numeric, numeric, numeric, numeric); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.ecef2neu(dx numeric, dy numeric, dz numeric, lat numeric, lon numeric) RETURNS double precision[]
    LANGUAGE sql
    AS $_$
select 
array[-sin(radians($4))*cos(radians($5))*$1 - sin(radians($4))*sin(radians($5))*$2 + cos(radians($4))*$3::numeric,
      -sin(radians($5))*$1 + cos(radians($5))*$2::numeric,
      cos(radians($4))*cos(radians($5))*$1 + cos(radians($4))*sin(radians($5))*$2 + sin(radians($4))*$3::numeric];

$_$;


ALTER FUNCTION public.ecef2neu(dx numeric, dy numeric, dz numeric, lat numeric, lon numeric) OWNER TO postgres;

--
-- TOC entry 349 (class 1255 OID 16588)
-- Name: fyear(numeric, numeric, numeric, numeric, numeric); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.fyear("Year" numeric, "DOY" numeric, "Hour" numeric DEFAULT 12, "Minute" numeric DEFAULT 0, "Second" numeric DEFAULT 0) RETURNS numeric
    LANGUAGE sql
    AS $_$
SELECT CASE 
WHEN isleapyear(cast($1 as integer)) = True  THEN $1 + ($2 + $3/24 + $4/1440 + $5/86400)/366
WHEN isleapyear(cast($1 as integer)) = False THEN $1 + ($2 + $3/24 + $4/1440 + $5/86400)/365
END;

$_$;


ALTER FUNCTION public.fyear("Year" numeric, "DOY" numeric, "Hour" numeric, "Minute" numeric, "Second" numeric) OWNER TO postgres;

--
-- TOC entry 350 (class 1255 OID 16589)
-- Name: horizdist(double precision[]); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.horizdist(neu double precision[]) RETURNS double precision
    LANGUAGE sql
    AS $_$

select 
sqrt(($1)[1]^2 + ($1)[2]^2 + ($1)[3]^2)

$_$;


ALTER FUNCTION public.horizdist(neu double precision[]) OWNER TO postgres;

--
-- TOC entry 351 (class 1255 OID 16590)
-- Name: isleapyear(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.isleapyear(year integer) RETURNS boolean
    LANGUAGE sql IMMUTABLE STRICT
    AS $_$
SELECT ($1 % 4 = 0) AND (($1 % 100 <> 0) or ($1 % 400 = 0))
$_$;


ALTER FUNCTION public.isleapyear(year integer) OWNER TO postgres;

--
-- TOC entry 352 (class 1255 OID 16591)
-- Name: stationalias_check(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.stationalias_check() RETURNS trigger
    LANGUAGE plpgsql
    AS $$DECLARE
	stnalias BOOLEAN;
BEGIN
SELECT (SELECT "StationCode" FROM stations WHERE "StationCode" = new."StationAlias") IS NULL INTO stnalias;
IF stnalias THEN
    RETURN NEW;
ELSE
	RAISE EXCEPTION 'Invalid station alias: already exists as a station code';
END IF;
END
$$;


ALTER FUNCTION public.stationalias_check() OWNER TO postgres;

--
-- TOC entry 355 (class 1255 OID 571414)
-- Name: update_has_gaps_update_needed_field(); Type: FUNCTION; Schema: public; Owner: gnss_data_osu
--

CREATE FUNCTION public.update_has_gaps_update_needed_field() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        IF (TG_OP = 'DELETE') THEN
            UPDATE api_stationmeta 
            SET has_gaps_update_needed = true 
            WHERE station_id = (
            SELECT api_id 
            FROM stations s 
            WHERE s."NetworkCode" = OLD."NetworkCode" and s."StationCode" = OLD."StationCode" 
            );
            RETURN OLD;
        ELSE
            UPDATE api_stationmeta 
            SET has_gaps_update_needed = true 
            WHERE station_id = (
            SELECT api_id 
            FROM stations s 
            WHERE s."NetworkCode" = NEW."NetworkCode" and s."StationCode" = NEW."StationCode" 
            );
            RETURN NEW;
        END IF;
    END;
    $$;


ALTER FUNCTION public.update_has_gaps_update_needed_field() OWNER TO gnss_data_osu;

--
-- TOC entry 356 (class 1255 OID 571417)
-- Name: update_has_stationinfo_field(); Type: FUNCTION; Schema: public; Owner: gnss_data_osu
--

CREATE FUNCTION public.update_has_stationinfo_field() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        IF (TG_OP = 'DELETE') THEN
            UPDATE api_stationmeta 
            SET has_stationinfo = EXISTS (SELECT 1 FROM stationinfo si where si."NetworkCode" = OLD."NetworkCode" and si."StationCode" = OLD."StationCode" )
            WHERE station_id = (
            SELECT api_id 
            FROM stations s 
            WHERE s."NetworkCode" = OLD."NetworkCode" and s."StationCode" = OLD."StationCode" 
            );
            RETURN OLD;
        ELSE
            UPDATE api_stationmeta 
            SET has_stationinfo = true 
            WHERE station_id = (
            SELECT api_id 
            FROM stations s 
            WHERE s."NetworkCode" = NEW."NetworkCode" and s."StationCode" = NEW."StationCode" 
            );
            RETURN NEW;
        END IF;
    END;
    $$;


ALTER FUNCTION public.update_has_stationinfo_field() OWNER TO gnss_data_osu;

--
-- TOC entry 353 (class 1255 OID 16592)
-- Name: update_station_timespan(character varying, character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_station_timespan("NetworkCode" character varying, "StationCode" character varying) RETURNS void
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
-- TOC entry 354 (class 1255 OID 16593)
-- Name: update_timespan_trigg(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_timespan_trigg() RETURNS trigger
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

SET default_table_access_method = heap;

--
-- TOC entry 215 (class 1259 OID 86862)
-- Name: antennas; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.antennas (
    "AntennaCode" character varying(22) NOT NULL,
    "AntennaDescription" character varying,
    api_id integer NOT NULL
);


ALTER TABLE public.antennas OWNER TO gnss_data_osu;

--
-- TOC entry 252 (class 1259 OID 567196)
-- Name: antennas_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.antennas_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.antennas_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4086 (class 0 OID 0)
-- Dependencies: 252
-- Name: antennas_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.antennas_api_id_seq OWNED BY public.antennas.api_id;


--
-- TOC entry 290 (class 1259 OID 570998)
-- Name: api_campaigns; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_campaigns (
    id bigint NOT NULL,
    name character varying(100) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL
);


ALTER TABLE public.api_campaigns OWNER TO gnss_data_osu;

--
-- TOC entry 289 (class 1259 OID 570997)
-- Name: api_campaigns_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_campaigns ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_campaigns_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 292 (class 1259 OID 571004)
-- Name: api_clustertype; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_clustertype (
    id bigint NOT NULL,
    name character varying(100) NOT NULL
);


ALTER TABLE public.api_clustertype OWNER TO gnss_data_osu;

--
-- TOC entry 291 (class 1259 OID 571003)
-- Name: api_clustertype_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_clustertype ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_clustertype_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 294 (class 1259 OID 571012)
-- Name: api_country; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_country (
    id bigint NOT NULL,
    name character varying(100) NOT NULL,
    two_digits_code character varying(2) NOT NULL,
    three_digits_code character varying(3) NOT NULL
);


ALTER TABLE public.api_country OWNER TO gnss_data_osu;

--
-- TOC entry 293 (class 1259 OID 571011)
-- Name: api_country_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_country ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_country_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 296 (class 1259 OID 571024)
-- Name: api_endpoint; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_endpoint (
    id bigint NOT NULL,
    path character varying(100) NOT NULL,
    description character varying(100) NOT NULL,
    method character varying(6) NOT NULL
);


ALTER TABLE public.api_endpoint OWNER TO gnss_data_osu;

--
-- TOC entry 295 (class 1259 OID 571023)
-- Name: api_endpoint_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_endpoint ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_endpoint_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 298 (class 1259 OID 571030)
-- Name: api_endpointscluster; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_endpointscluster (
    id bigint NOT NULL,
    description character varying(100) NOT NULL,
    role_type character varying(15) NOT NULL,
    cluster_type_id bigint NOT NULL,
    resource_id bigint NOT NULL
);


ALTER TABLE public.api_endpointscluster OWNER TO gnss_data_osu;

--
-- TOC entry 336 (class 1259 OID 571183)
-- Name: api_endpointscluster_endpoints; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_endpointscluster_endpoints (
    id bigint NOT NULL,
    endpointscluster_id bigint NOT NULL,
    endpoint_id bigint NOT NULL
);


ALTER TABLE public.api_endpointscluster_endpoints OWNER TO gnss_data_osu;

--
-- TOC entry 335 (class 1259 OID 571182)
-- Name: api_endpointscluster_endpoints_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_endpointscluster_endpoints ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_endpointscluster_endpoints_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 297 (class 1259 OID 571029)
-- Name: api_endpointscluster_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_endpointscluster ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_endpointscluster_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 300 (class 1259 OID 571036)
-- Name: api_monumenttype; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_monumenttype (
    id bigint NOT NULL,
    name character varying(100) NOT NULL,
    photo_path character varying(100) NOT NULL
);


ALTER TABLE public.api_monumenttype OWNER TO gnss_data_osu;

--
-- TOC entry 299 (class 1259 OID 571035)
-- Name: api_monumenttype_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_monumenttype ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_monumenttype_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 302 (class 1259 OID 571044)
-- Name: api_person; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_person (
    id bigint NOT NULL,
    first_name character varying(100) NOT NULL,
    last_name character varying(100) NOT NULL,
    email character varying(100) NOT NULL,
    phone character varying(15) NOT NULL,
    address character varying(100) NOT NULL,
    photo character varying(100) NOT NULL,
    user_id bigint
);


ALTER TABLE public.api_person OWNER TO gnss_data_osu;

--
-- TOC entry 301 (class 1259 OID 571043)
-- Name: api_person_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_person ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_person_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 304 (class 1259 OID 571052)
-- Name: api_resource; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_resource (
    id bigint NOT NULL,
    name character varying(100) NOT NULL
);


ALTER TABLE public.api_resource OWNER TO gnss_data_osu;

--
-- TOC entry 303 (class 1259 OID 571051)
-- Name: api_resource_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_resource ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_resource_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 306 (class 1259 OID 571060)
-- Name: api_role; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_role (
    id bigint NOT NULL,
    name character varying(100) NOT NULL,
    role_api boolean NOT NULL,
    allow_all boolean NOT NULL,
    is_active boolean NOT NULL
);


ALTER TABLE public.api_role OWNER TO gnss_data_osu;

--
-- TOC entry 338 (class 1259 OID 571199)
-- Name: api_role_endpoints_clusters; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_role_endpoints_clusters (
    id bigint NOT NULL,
    role_id bigint NOT NULL,
    endpointscluster_id bigint NOT NULL
);


ALTER TABLE public.api_role_endpoints_clusters OWNER TO gnss_data_osu;

--
-- TOC entry 337 (class 1259 OID 571198)
-- Name: api_role_endpoints_clusters_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_role_endpoints_clusters ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_role_endpoints_clusters_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 305 (class 1259 OID 571059)
-- Name: api_role_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_role ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_role_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 308 (class 1259 OID 571068)
-- Name: api_rolepersonstation; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_rolepersonstation (
    id bigint NOT NULL,
    person_id bigint NOT NULL,
    station_id integer NOT NULL,
    role_id bigint NOT NULL
);


ALTER TABLE public.api_rolepersonstation OWNER TO gnss_data_osu;

--
-- TOC entry 307 (class 1259 OID 571067)
-- Name: api_rolepersonstation_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_rolepersonstation ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_rolepersonstation_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 310 (class 1259 OID 571074)
-- Name: api_stationattachedfiles; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_stationattachedfiles (
    id bigint NOT NULL,
    file character varying(100) NOT NULL,
    filename character varying(255) NOT NULL,
    description character varying(500) NOT NULL,
    station_id integer NOT NULL
);


ALTER TABLE public.api_stationattachedfiles OWNER TO gnss_data_osu;

--
-- TOC entry 309 (class 1259 OID 571073)
-- Name: api_stationattachedfiles_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_stationattachedfiles ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_stationattachedfiles_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 312 (class 1259 OID 571082)
-- Name: api_stationimages; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_stationimages (
    id bigint NOT NULL,
    image character varying(100) NOT NULL,
    name character varying(255) NOT NULL,
    description character varying(500) NOT NULL,
    station_id integer NOT NULL
);


ALTER TABLE public.api_stationimages OWNER TO gnss_data_osu;

--
-- TOC entry 311 (class 1259 OID 571081)
-- Name: api_stationimages_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_stationimages ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_stationimages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 314 (class 1259 OID 571090)
-- Name: api_stationmeta; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_stationmeta (
    id bigint NOT NULL,
    remote_access_link character varying(500) NOT NULL,
    has_battery boolean NOT NULL,
    battery_description character varying(100) NOT NULL,
    has_communications boolean NOT NULL,
    communications_description character varying(100) NOT NULL,
    comments character varying NOT NULL,
    navigation_file character varying(100) NOT NULL,
    navigation_filename character varying(255) NOT NULL,
    has_gaps boolean NOT NULL,
    has_gaps_last_update_datetime timestamp with time zone,
    has_gaps_update_needed boolean NOT NULL,
    has_stationinfo boolean NOT NULL,
    monument_type_id bigint,
    station_id integer NOT NULL,
    status_id bigint,
    station_type_id bigint
);


ALTER TABLE public.api_stationmeta OWNER TO gnss_data_osu;

--
-- TOC entry 313 (class 1259 OID 571089)
-- Name: api_stationmeta_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_stationmeta ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_stationmeta_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 347 (class 1259 OID 572134)
-- Name: api_stationmetagaps; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_stationmetagaps (
    id bigint NOT NULL,
    rinex_count integer NOT NULL,
    record_start_date_start timestamp with time zone,
    record_start_date_end timestamp with time zone,
    record_end_date_start timestamp with time zone,
    record_end_date_end timestamp with time zone,
    station_meta_id bigint NOT NULL
);


ALTER TABLE public.api_stationmetagaps OWNER TO gnss_data_osu;

--
-- TOC entry 346 (class 1259 OID 572133)
-- Name: api_stationmetagaps_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_stationmetagaps ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_stationmetagaps_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 316 (class 1259 OID 571098)
-- Name: api_stationrole; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_stationrole (
    id bigint NOT NULL,
    name character varying(100) NOT NULL
);


ALTER TABLE public.api_stationrole OWNER TO gnss_data_osu;

--
-- TOC entry 315 (class 1259 OID 571097)
-- Name: api_stationrole_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_stationrole ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_stationrole_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 318 (class 1259 OID 571106)
-- Name: api_stationstatus; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_stationstatus (
    id bigint NOT NULL,
    name character varying(100) NOT NULL
);


ALTER TABLE public.api_stationstatus OWNER TO gnss_data_osu;

--
-- TOC entry 317 (class 1259 OID 571105)
-- Name: api_stationstatus_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_stationstatus ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_stationstatus_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 320 (class 1259 OID 571114)
-- Name: api_stationtype; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_stationtype (
    id bigint NOT NULL,
    name character varying(100) NOT NULL
);


ALTER TABLE public.api_stationtype OWNER TO gnss_data_osu;

--
-- TOC entry 319 (class 1259 OID 571113)
-- Name: api_stationtype_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_stationtype ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_stationtype_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 330 (class 1259 OID 571154)
-- Name: api_user; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_user (
    id bigint NOT NULL,
    password character varying(128) NOT NULL,
    last_login timestamp with time zone,
    is_superuser boolean NOT NULL,
    username character varying(150) NOT NULL,
    first_name character varying(150) NOT NULL,
    last_name character varying(150) NOT NULL,
    email character varying(254) NOT NULL,
    is_staff boolean NOT NULL,
    is_active boolean NOT NULL,
    date_joined timestamp with time zone NOT NULL,
    phone character varying(15) NOT NULL,
    address character varying(100) NOT NULL,
    photo character varying(100) NOT NULL,
    role_id bigint NOT NULL
);


ALTER TABLE public.api_user OWNER TO gnss_data_osu;

--
-- TOC entry 332 (class 1259 OID 571164)
-- Name: api_user_groups; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_user_groups (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    group_id integer NOT NULL
);


ALTER TABLE public.api_user_groups OWNER TO gnss_data_osu;

--
-- TOC entry 331 (class 1259 OID 571163)
-- Name: api_user_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_user_groups ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_user_groups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 329 (class 1259 OID 571153)
-- Name: api_user_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_user ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 334 (class 1259 OID 571170)
-- Name: api_user_user_permissions; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_user_user_permissions (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    permission_id integer NOT NULL
);


ALTER TABLE public.api_user_user_permissions OWNER TO gnss_data_osu;

--
-- TOC entry 333 (class 1259 OID 571169)
-- Name: api_user_user_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_user_user_permissions ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_user_user_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 322 (class 1259 OID 571122)
-- Name: api_visitattachedfiles; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_visitattachedfiles (
    id bigint NOT NULL,
    file character varying(100) NOT NULL,
    filename character varying(255) NOT NULL,
    description character varying(500) NOT NULL,
    visit_id bigint NOT NULL
);


ALTER TABLE public.api_visitattachedfiles OWNER TO gnss_data_osu;

--
-- TOC entry 321 (class 1259 OID 571121)
-- Name: api_visitattachedfiles_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_visitattachedfiles ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_visitattachedfiles_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 324 (class 1259 OID 571130)
-- Name: api_visitgnssdatafiles; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_visitgnssdatafiles (
    id bigint NOT NULL,
    file character varying(100) NOT NULL,
    filename character varying(255) NOT NULL,
    description character varying(500) NOT NULL,
    visit_id bigint NOT NULL
);


ALTER TABLE public.api_visitgnssdatafiles OWNER TO gnss_data_osu;

--
-- TOC entry 323 (class 1259 OID 571129)
-- Name: api_visitgnssdatafiles_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_visitgnssdatafiles ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_visitgnssdatafiles_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 326 (class 1259 OID 571138)
-- Name: api_visitimages; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_visitimages (
    id bigint NOT NULL,
    image character varying(100) NOT NULL,
    name character varying(255) NOT NULL,
    description character varying(500) NOT NULL,
    visit_id bigint NOT NULL
);


ALTER TABLE public.api_visitimages OWNER TO gnss_data_osu;

--
-- TOC entry 325 (class 1259 OID 571137)
-- Name: api_visitimages_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_visitimages ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_visitimages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 328 (class 1259 OID 571146)
-- Name: api_visits; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_visits (
    id bigint NOT NULL,
    date date NOT NULL,
    log_sheet_file character varying(100),
    log_sheet_filename character varying(255) NOT NULL,
    navigation_file character varying(100) NOT NULL,
    navigation_filename character varying(255) NOT NULL,
    campaign_id bigint,
    station_id integer NOT NULL,
    comments character varying NOT NULL
);


ALTER TABLE public.api_visits OWNER TO gnss_data_osu;

--
-- TOC entry 327 (class 1259 OID 571145)
-- Name: api_visits_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_visits ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_visits_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 340 (class 1259 OID 571260)
-- Name: api_visits_people; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.api_visits_people (
    id bigint NOT NULL,
    visits_id bigint NOT NULL,
    person_id bigint NOT NULL
);


ALTER TABLE public.api_visits_people OWNER TO gnss_data_osu;

--
-- TOC entry 339 (class 1259 OID 571259)
-- Name: api_visits_people_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.api_visits_people ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.api_visits_people_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 216 (class 1259 OID 86868)
-- Name: apr_coords; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.apr_coords (
    "NetworkCode" character varying NOT NULL,
    "StationCode" character varying NOT NULL,
    "FYear" numeric,
    x numeric,
    y numeric,
    z numeric,
    sn numeric,
    se numeric,
    su numeric,
    "ReferenceFrame" character varying(20),
    "Year" integer NOT NULL,
    "DOY" integer NOT NULL,
    api_id integer NOT NULL
);


ALTER TABLE public.apr_coords OWNER TO gnss_data_osu;

--
-- TOC entry 253 (class 1259 OID 567206)
-- Name: apr_coords_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.apr_coords_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.apr_coords_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4087 (class 0 OID 0)
-- Dependencies: 253
-- Name: apr_coords_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.apr_coords_api_id_seq OWNED BY public.apr_coords.api_id;


--
-- TOC entry 344 (class 1259 OID 571427)
-- Name: auditlog_logentry; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.auditlog_logentry (
    id integer NOT NULL,
    object_pk character varying(255) NOT NULL,
    object_id bigint,
    object_repr text NOT NULL,
    action smallint NOT NULL,
    changes jsonb,
    "timestamp" timestamp with time zone NOT NULL,
    actor_id bigint,
    content_type_id integer NOT NULL,
    remote_addr inet,
    additional_data jsonb,
    serialized_data jsonb,
    cid character varying(255),
    changes_text text NOT NULL,
    CONSTRAINT auditlog_logentry_action_check CHECK ((action >= 0))
);


ALTER TABLE public.auditlog_logentry OWNER TO gnss_data_osu;

--
-- TOC entry 343 (class 1259 OID 571426)
-- Name: auditlog_logentry_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.auditlog_logentry ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auditlog_logentry_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 286 (class 1259 OID 570958)
-- Name: auth_group; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.auth_group (
    id integer NOT NULL,
    name character varying(150) NOT NULL
);


ALTER TABLE public.auth_group OWNER TO gnss_data_osu;

--
-- TOC entry 285 (class 1259 OID 570957)
-- Name: auth_group_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.auth_group ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_group_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 288 (class 1259 OID 570966)
-- Name: auth_group_permissions; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.auth_group_permissions (
    id bigint NOT NULL,
    group_id integer NOT NULL,
    permission_id integer NOT NULL
);


ALTER TABLE public.auth_group_permissions OWNER TO gnss_data_osu;

--
-- TOC entry 287 (class 1259 OID 570965)
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.auth_group_permissions ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_group_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 284 (class 1259 OID 570952)
-- Name: auth_permission; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.auth_permission (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    content_type_id integer NOT NULL,
    codename character varying(100) NOT NULL
);


ALTER TABLE public.auth_permission OWNER TO gnss_data_osu;

--
-- TOC entry 283 (class 1259 OID 570951)
-- Name: auth_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.auth_permission ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_permission_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 217 (class 1259 OID 86874)
-- Name: aws_sync; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.aws_sync (
    "NetworkCode" character varying NOT NULL,
    "StationCode" character varying NOT NULL,
    "StationAlias" character varying(4) NOT NULL,
    "Year" numeric NOT NULL,
    "DOY" numeric NOT NULL,
    sync_date timestamp without time zone,
    api_id integer NOT NULL
);


ALTER TABLE public.aws_sync OWNER TO gnss_data_osu;

--
-- TOC entry 254 (class 1259 OID 567217)
-- Name: aws_sync_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.aws_sync_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.aws_sync_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4088 (class 0 OID 0)
-- Dependencies: 254
-- Name: aws_sync_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.aws_sync_api_id_seq OWNED BY public.aws_sync.api_id;


--
-- TOC entry 247 (class 1259 OID 556348)
-- Name: data_source; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.data_source (
    "NetworkCode" character varying(3) NOT NULL,
    "StationCode" character varying(4) NOT NULL,
    try_order numeric NOT NULL,
    protocol character varying NOT NULL,
    fqdn character varying NOT NULL,
    username character varying,
    password character varying,
    path character varying,
    format character varying,
    api_id integer NOT NULL
);


ALTER TABLE public.data_source OWNER TO gnss_data_osu;

--
-- TOC entry 255 (class 1259 OID 567228)
-- Name: data_source_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.data_source_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.data_source_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4089 (class 0 OID 0)
-- Dependencies: 255
-- Name: data_source_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.data_source_api_id_seq OWNED BY public.data_source.api_id;


--
-- TOC entry 342 (class 1259 OID 571393)
-- Name: django_admin_log; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.django_admin_log (
    id integer NOT NULL,
    action_time timestamp with time zone NOT NULL,
    object_id text,
    object_repr character varying(200) NOT NULL,
    action_flag smallint NOT NULL,
    change_message text NOT NULL,
    content_type_id integer,
    user_id bigint NOT NULL,
    CONSTRAINT django_admin_log_action_flag_check CHECK ((action_flag >= 0))
);


ALTER TABLE public.django_admin_log OWNER TO gnss_data_osu;

--
-- TOC entry 341 (class 1259 OID 571392)
-- Name: django_admin_log_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.django_admin_log ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_admin_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 282 (class 1259 OID 570944)
-- Name: django_content_type; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.django_content_type (
    id integer NOT NULL,
    app_label character varying(100) NOT NULL,
    model character varying(100) NOT NULL
);


ALTER TABLE public.django_content_type OWNER TO gnss_data_osu;

--
-- TOC entry 281 (class 1259 OID 570943)
-- Name: django_content_type_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.django_content_type ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_content_type_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 280 (class 1259 OID 570936)
-- Name: django_migrations; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.django_migrations (
    id bigint NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


ALTER TABLE public.django_migrations OWNER TO gnss_data_osu;

--
-- TOC entry 279 (class 1259 OID 570935)
-- Name: django_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.django_migrations ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_migrations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 345 (class 1259 OID 571490)
-- Name: django_session; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.django_session (
    session_key character varying(40) NOT NULL,
    session_data text NOT NULL,
    expire_date timestamp with time zone NOT NULL
);


ALTER TABLE public.django_session OWNER TO gnss_data_osu;

--
-- TOC entry 218 (class 1259 OID 86880)
-- Name: earthquakes; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.earthquakes (
    date timestamp without time zone NOT NULL,
    lat numeric NOT NULL,
    lon numeric NOT NULL,
    depth numeric,
    mag numeric,
    strike1 numeric,
    dip1 numeric,
    rake1 numeric,
    strike2 numeric,
    dip2 numeric,
    rake2 numeric,
    id character varying(40),
    location character varying(120),
    api_id integer NOT NULL
);


ALTER TABLE public.earthquakes OWNER TO gnss_data_osu;

--
-- TOC entry 256 (class 1259 OID 567238)
-- Name: earthquakes_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.earthquakes_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.earthquakes_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4090 (class 0 OID 0)
-- Dependencies: 256
-- Name: earthquakes_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.earthquakes_api_id_seq OWNED BY public.earthquakes.api_id;


--
-- TOC entry 219 (class 1259 OID 86886)
-- Name: etm_params_uid_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.etm_params_uid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.etm_params_uid_seq OWNER TO gnss_data_osu;

--
-- TOC entry 220 (class 1259 OID 86888)
-- Name: etm_params; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.etm_params (
    "NetworkCode" character varying(3) NOT NULL,
    "StationCode" character varying(4) NOT NULL,
    soln character varying(10) NOT NULL,
    object character varying(10) NOT NULL,
    terms numeric,
    frequencies numeric[],
    jump_type numeric,
    relaxation numeric[],
    "Year" numeric,
    "DOY" numeric,
    action character varying(1),
    uid integer DEFAULT nextval('public.etm_params_uid_seq'::regclass) NOT NULL
);


ALTER TABLE public.etm_params OWNER TO gnss_data_osu;

--
-- TOC entry 221 (class 1259 OID 86895)
-- Name: etmsv2_uid_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.etmsv2_uid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.etmsv2_uid_seq OWNER TO gnss_data_osu;

--
-- TOC entry 222 (class 1259 OID 86897)
-- Name: etms; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.etms (
    "NetworkCode" character varying(3) NOT NULL,
    "StationCode" character varying(4) NOT NULL,
    soln character varying(10) NOT NULL,
    object character varying(10) NOT NULL,
    t_ref numeric,
    jump_type numeric,
    relaxation numeric[],
    frequencies numeric[],
    params numeric[],
    sigmas numeric[],
    metadata text,
    hash numeric,
    jump_date timestamp without time zone,
    uid integer DEFAULT nextval('public.etmsv2_uid_seq'::regclass) NOT NULL,
    stack character varying(20)
);


ALTER TABLE public.etms OWNER TO gnss_data_osu;

--
-- TOC entry 223 (class 1259 OID 86904)
-- Name: events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.events_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.events_event_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 224 (class 1259 OID 86906)
-- Name: events; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.events (
    event_id bigint DEFAULT nextval('public.events_event_id_seq'::regclass) NOT NULL,
    "EventDate" timestamp without time zone DEFAULT now() NOT NULL,
    "EventType" character varying(6),
    "NetworkCode" character varying(3),
    "StationCode" character varying(4),
    "Year" integer,
    "DOY" integer,
    "Description" text,
    stack text,
    module text,
    node text
);


ALTER TABLE public.events OWNER TO gnss_data_osu;

--
-- TOC entry 225 (class 1259 OID 86914)
-- Name: executions_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.executions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.executions_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 226 (class 1259 OID 86916)
-- Name: executions; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.executions (
    id integer DEFAULT nextval('public.executions_id_seq'::regclass) NOT NULL,
    script character varying(40),
    exec_date timestamp without time zone DEFAULT now(),
    api_id integer NOT NULL
);


ALTER TABLE public.executions OWNER TO gnss_data_osu;

--
-- TOC entry 257 (class 1259 OID 567248)
-- Name: executions_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.executions_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.executions_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4091 (class 0 OID 0)
-- Dependencies: 257
-- Name: executions_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.executions_api_id_seq OWNED BY public.executions.api_id;


--
-- TOC entry 227 (class 1259 OID 86921)
-- Name: gamit_htc; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.gamit_htc (
    "AntennaCode" character varying(22) NOT NULL,
    "HeightCode" character varying(5) NOT NULL,
    v_offset numeric,
    h_offset numeric,
    api_id integer NOT NULL
);


ALTER TABLE public.gamit_htc OWNER TO gnss_data_osu;

--
-- TOC entry 258 (class 1259 OID 567255)
-- Name: gamit_htc_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.gamit_htc_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.gamit_htc_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4092 (class 0 OID 0)
-- Dependencies: 258
-- Name: gamit_htc_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.gamit_htc_api_id_seq OWNED BY public.gamit_htc.api_id;


--
-- TOC entry 228 (class 1259 OID 86927)
-- Name: gamit_soln; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.gamit_soln (
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
    sigmaxz numeric,
    api_id integer NOT NULL
);


ALTER TABLE public.gamit_soln OWNER TO gnss_data_osu;

--
-- TOC entry 259 (class 1259 OID 567265)
-- Name: gamit_soln_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.gamit_soln_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.gamit_soln_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4093 (class 0 OID 0)
-- Dependencies: 259
-- Name: gamit_soln_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.gamit_soln_api_id_seq OWNED BY public.gamit_soln.api_id;


--
-- TOC entry 229 (class 1259 OID 86933)
-- Name: gamit_soln_excl; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.gamit_soln_excl (
    "NetworkCode" character varying(3) NOT NULL,
    "StationCode" character varying(4) NOT NULL,
    "Project" character varying(20) NOT NULL,
    "Year" bigint NOT NULL,
    "DOY" bigint NOT NULL,
    residual numeric,
    api_id integer NOT NULL
);


ALTER TABLE public.gamit_soln_excl OWNER TO gnss_data_osu;

--
-- TOC entry 260 (class 1259 OID 567275)
-- Name: gamit_soln_excl_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.gamit_soln_excl_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.gamit_soln_excl_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4094 (class 0 OID 0)
-- Dependencies: 260
-- Name: gamit_soln_excl_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.gamit_soln_excl_api_id_seq OWNED BY public.gamit_soln_excl.api_id;


--
-- TOC entry 230 (class 1259 OID 86939)
-- Name: gamit_stats; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.gamit_stats (
    "Project" character varying(20) NOT NULL,
    subnet numeric NOT NULL,
    "Year" numeric NOT NULL,
    "DOY" numeric NOT NULL,
    "FYear" numeric,
    wl numeric,
    nl numeric,
    nrms numeric,
    relaxed_constrains text,
    max_overconstrained character varying(8),
    updated_apr text,
    iterations numeric,
    node character varying(50),
    execution_time numeric,
    execution_date timestamp without time zone,
    system character(1) NOT NULL,
    api_id integer NOT NULL
);


ALTER TABLE public.gamit_stats OWNER TO gnss_data_osu;

--
-- TOC entry 261 (class 1259 OID 567285)
-- Name: gamit_stats_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.gamit_stats_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.gamit_stats_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4095 (class 0 OID 0)
-- Dependencies: 261
-- Name: gamit_stats_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.gamit_stats_api_id_seq OWNED BY public.gamit_stats.api_id;


--
-- TOC entry 231 (class 1259 OID 86945)
-- Name: gamit_subnets; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.gamit_subnets (
    "Project" character varying(20) NOT NULL,
    subnet numeric NOT NULL,
    "Year" numeric NOT NULL,
    "DOY" numeric NOT NULL,
    centroid numeric[],
    stations character varying[],
    alias character varying[],
    ties character varying[],
    api_id integer NOT NULL
);


ALTER TABLE public.gamit_subnets OWNER TO gnss_data_osu;

--
-- TOC entry 262 (class 1259 OID 567295)
-- Name: gamit_subnets_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.gamit_subnets_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.gamit_subnets_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4096 (class 0 OID 0)
-- Dependencies: 262
-- Name: gamit_subnets_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.gamit_subnets_api_id_seq OWNED BY public.gamit_subnets.api_id;


--
-- TOC entry 232 (class 1259 OID 86951)
-- Name: gamit_ztd; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.gamit_ztd (
    "NetworkCode" character varying(3) NOT NULL,
    "StationCode" character varying(4) NOT NULL,
    "Date" timestamp without time zone NOT NULL,
    "Project" character varying(20) NOT NULL,
    "Year" numeric NOT NULL,
    "DOY" numeric NOT NULL,
    "ZTD" numeric NOT NULL,
    model numeric,
    sigma numeric,
    api_id integer NOT NULL
);


ALTER TABLE public.gamit_ztd OWNER TO gnss_data_osu;

--
-- TOC entry 263 (class 1259 OID 567305)
-- Name: gamit_ztd_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.gamit_ztd_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.gamit_ztd_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4097 (class 0 OID 0)
-- Dependencies: 263
-- Name: gamit_ztd_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.gamit_ztd_api_id_seq OWNED BY public.gamit_ztd.api_id;


--
-- TOC entry 233 (class 1259 OID 86957)
-- Name: keys; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.keys (
    "KeyCode" character varying(7) NOT NULL,
    "TotalChars" integer,
    rinex_col_out character varying,
    rinex_col_in character varying(60),
    isnumeric bit(1),
    api_id integer NOT NULL
);


ALTER TABLE public.keys OWNER TO gnss_data_osu;

--
-- TOC entry 264 (class 1259 OID 567317)
-- Name: keys_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.keys_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.keys_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4098 (class 0 OID 0)
-- Dependencies: 264
-- Name: keys_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.keys_api_id_seq OWNED BY public.keys.api_id;


--
-- TOC entry 234 (class 1259 OID 86963)
-- Name: locks; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.locks (
    filename text NOT NULL,
    "NetworkCode" character varying(3),
    "StationCode" character varying(4),
    api_id integer NOT NULL
);


ALTER TABLE public.locks OWNER TO gnss_data_osu;

--
-- TOC entry 265 (class 1259 OID 567327)
-- Name: locks_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.locks_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.locks_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4099 (class 0 OID 0)
-- Dependencies: 265
-- Name: locks_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.locks_api_id_seq OWNED BY public.locks.api_id;


--
-- TOC entry 235 (class 1259 OID 86969)
-- Name: networks; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.networks (
    "NetworkCode" character varying NOT NULL,
    "NetworkName" character varying,
    api_id integer NOT NULL
);


ALTER TABLE public.networks OWNER TO gnss_data_osu;

--
-- TOC entry 266 (class 1259 OID 567337)
-- Name: networks_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.networks_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.networks_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4100 (class 0 OID 0)
-- Dependencies: 266
-- Name: networks_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.networks_api_id_seq OWNED BY public.networks.api_id;


--
-- TOC entry 236 (class 1259 OID 86975)
-- Name: ppp_soln; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.ppp_soln (
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
    sigmayz numeric,
    hash integer,
    api_id integer NOT NULL
);


ALTER TABLE public.ppp_soln OWNER TO gnss_data_osu;

--
-- TOC entry 267 (class 1259 OID 567347)
-- Name: ppp_soln_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.ppp_soln_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ppp_soln_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4101 (class 0 OID 0)
-- Dependencies: 267
-- Name: ppp_soln_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.ppp_soln_api_id_seq OWNED BY public.ppp_soln.api_id;


--
-- TOC entry 237 (class 1259 OID 86981)
-- Name: ppp_soln_excl; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.ppp_soln_excl (
    "NetworkCode" character varying(3) NOT NULL,
    "StationCode" character varying(4) NOT NULL,
    "Year" numeric NOT NULL,
    "DOY" numeric NOT NULL,
    api_id integer NOT NULL
);


ALTER TABLE public.ppp_soln_excl OWNER TO gnss_data_osu;

--
-- TOC entry 268 (class 1259 OID 567359)
-- Name: ppp_soln_excl_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.ppp_soln_excl_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ppp_soln_excl_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4102 (class 0 OID 0)
-- Dependencies: 268
-- Name: ppp_soln_excl_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.ppp_soln_excl_api_id_seq OWNED BY public.ppp_soln_excl.api_id;


--
-- TOC entry 238 (class 1259 OID 86987)
-- Name: receivers; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.receivers (
    "ReceiverCode" character varying(22) NOT NULL,
    "ReceiverDescription" character varying(22),
    api_id integer NOT NULL
);


ALTER TABLE public.receivers OWNER TO gnss_data_osu;

--
-- TOC entry 269 (class 1259 OID 567369)
-- Name: receivers_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.receivers_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.receivers_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4103 (class 0 OID 0)
-- Dependencies: 269
-- Name: receivers_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.receivers_api_id_seq OWNED BY public.receivers.api_id;


--
-- TOC entry 239 (class 1259 OID 86990)
-- Name: rinex; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.rinex (
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
    "Filename" character varying(50),
    "Interval" numeric NOT NULL,
    "AntennaOffset" numeric,
    "Completion" numeric(7,3) NOT NULL,
    api_id integer NOT NULL
);


ALTER TABLE public.rinex OWNER TO gnss_data_osu;

--
-- TOC entry 270 (class 1259 OID 567377)
-- Name: rinex_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.rinex_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.rinex_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4104 (class 0 OID 0)
-- Dependencies: 270
-- Name: rinex_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.rinex_api_id_seq OWNED BY public.rinex.api_id;


--
-- TOC entry 240 (class 1259 OID 86996)
-- Name: rinex_proc; Type: VIEW; Schema: public; Owner: gnss_data_osu
--

CREATE VIEW public.rinex_proc AS
 SELECT "NetworkCode",
    "StationCode",
    "ObservationYear",
    "ObservationMonth",
    "ObservationDay",
    "ObservationDOY",
    "ObservationFYear",
    "ObservationSTime",
    "ObservationETime",
    "ReceiverType",
    "ReceiverSerial",
    "ReceiverFw",
    "AntennaType",
    "AntennaSerial",
    "AntennaDome",
    "Filename",
    "Interval",
    "AntennaOffset",
    "Completion",
    "mI"
   FROM ( SELECT aa."NetworkCode",
            aa."StationCode",
            aa."ObservationYear",
            aa."ObservationMonth",
            aa."ObservationDay",
            aa."ObservationDOY",
            aa."ObservationFYear",
            aa."ObservationSTime",
            aa."ObservationETime",
            aa."ReceiverType",
            aa."ReceiverSerial",
            aa."ReceiverFw",
            aa."AntennaType",
            aa."AntennaSerial",
            aa."AntennaDome",
            aa."Filename",
            aa."Interval",
            aa."AntennaOffset",
            aa."Completion",
            min(aa."Interval") OVER (PARTITION BY aa."NetworkCode", aa."StationCode", aa."ObservationYear", aa."ObservationDOY") AS "mI"
           FROM (public.rinex aa
             LEFT JOIN public.rinex bb ON ((((aa."NetworkCode")::text = (bb."NetworkCode")::text) AND ((aa."StationCode")::text = (bb."StationCode")::text) AND (aa."ObservationYear" = bb."ObservationYear") AND (aa."ObservationDOY" = bb."ObservationDOY") AND (aa."Completion" < bb."Completion"))))
          WHERE (bb."NetworkCode" IS NULL)
          ORDER BY aa."NetworkCode", aa."StationCode", aa."ObservationYear", aa."ObservationDOY", aa."Interval", aa."Completion") rnx
  WHERE ("Interval" = "mI");


ALTER VIEW public.rinex_proc OWNER TO gnss_data_osu;

--
-- TOC entry 241 (class 1259 OID 87001)
-- Name: rinex_sources_info; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.rinex_sources_info (
    name character varying(20) NOT NULL,
    fqdn character varying NOT NULL,
    protocol character varying NOT NULL,
    username character varying,
    password character varying,
    path character varying,
    format character varying,
    api_id integer NOT NULL
);


ALTER TABLE public.rinex_sources_info OWNER TO gnss_data_osu;

--
-- TOC entry 271 (class 1259 OID 567391)
-- Name: rinex_sources_info_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.rinex_sources_info_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.rinex_sources_info_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4105 (class 0 OID 0)
-- Dependencies: 271
-- Name: rinex_sources_info_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.rinex_sources_info_api_id_seq OWNED BY public.rinex_sources_info.api_id;


--
-- TOC entry 242 (class 1259 OID 87007)
-- Name: rinex_tank_struct; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.rinex_tank_struct (
    "Level" integer NOT NULL,
    "KeyCode" character varying(7),
    api_id integer NOT NULL
);


ALTER TABLE public.rinex_tank_struct OWNER TO gnss_data_osu;

--
-- TOC entry 272 (class 1259 OID 567401)
-- Name: rinex_tank_struct_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.rinex_tank_struct_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.rinex_tank_struct_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4106 (class 0 OID 0)
-- Dependencies: 272
-- Name: rinex_tank_struct_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.rinex_tank_struct_api_id_seq OWNED BY public.rinex_tank_struct.api_id;


--
-- TOC entry 248 (class 1259 OID 556361)
-- Name: sources_formats; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.sources_formats (
    format character varying NOT NULL,
    api_id integer NOT NULL
);


ALTER TABLE public.sources_formats OWNER TO gnss_data_osu;

--
-- TOC entry 273 (class 1259 OID 567409)
-- Name: sources_formats_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.sources_formats_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sources_formats_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4107 (class 0 OID 0)
-- Dependencies: 273
-- Name: sources_formats_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.sources_formats_api_id_seq OWNED BY public.sources_formats.api_id;


--
-- TOC entry 250 (class 1259 OID 556371)
-- Name: sources_servers; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.sources_servers (
    server_id integer NOT NULL,
    protocol character varying NOT NULL,
    fqdn character varying NOT NULL,
    username character varying,
    password character varying,
    path character varying,
    format character varying DEFAULT 'DEFAULT_FORMAT'::character varying NOT NULL,
    CONSTRAINT sources_servers_protocol_check CHECK (((protocol)::text = ANY (ARRAY[('ftp'::character varying)::text, ('http'::character varying)::text, ('sftp'::character varying)::text, ('https'::character varying)::text, ('ftpa'::character varying)::text, ('FTP'::character varying)::text, ('HTTP'::character varying)::text, ('SFTP'::character varying)::text, ('HTTPS'::character varying)::text, ('FTPA'::character varying)::text])))
);


ALTER TABLE public.sources_servers OWNER TO gnss_data_osu;

--
-- TOC entry 249 (class 1259 OID 556369)
-- Name: sources_servers_server_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.sources_servers ALTER COLUMN server_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.sources_servers_server_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 251 (class 1259 OID 556386)
-- Name: sources_stations; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.sources_stations (
    "NetworkCode" character varying(3) NOT NULL,
    "StationCode" character varying(4) NOT NULL,
    try_order smallint DEFAULT 1 NOT NULL,
    server_id integer NOT NULL,
    path character varying,
    format character varying,
    api_id integer NOT NULL
);


ALTER TABLE public.sources_stations OWNER TO gnss_data_osu;

--
-- TOC entry 274 (class 1259 OID 567419)
-- Name: sources_stations_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.sources_stations_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sources_stations_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4108 (class 0 OID 0)
-- Dependencies: 274
-- Name: sources_stations_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.sources_stations_api_id_seq OWNED BY public.sources_stations.api_id;


--
-- TOC entry 243 (class 1259 OID 87010)
-- Name: stacks; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.stacks (
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
    sigmaxz numeric,
    name character varying(20) NOT NULL,
    api_id integer NOT NULL
);


ALTER TABLE public.stacks OWNER TO gnss_data_osu;

--
-- TOC entry 275 (class 1259 OID 567429)
-- Name: stacks_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.stacks_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stacks_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4109 (class 0 OID 0)
-- Dependencies: 275
-- Name: stacks_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.stacks_api_id_seq OWNED BY public.stacks.api_id;


--
-- TOC entry 244 (class 1259 OID 87016)
-- Name: stationalias; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.stationalias (
    "NetworkCode" character varying(3) NOT NULL,
    "StationCode" character varying(4) NOT NULL,
    "StationAlias" character varying(4) NOT NULL,
    api_id integer NOT NULL
);


ALTER TABLE public.stationalias OWNER TO gnss_data_osu;

--
-- TOC entry 276 (class 1259 OID 567440)
-- Name: stationalias_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.stationalias_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stationalias_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4110 (class 0 OID 0)
-- Dependencies: 276
-- Name: stationalias_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.stationalias_api_id_seq OWNED BY public.stationalias.api_id;


--
-- TOC entry 245 (class 1259 OID 87019)
-- Name: stationinfo; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.stationinfo (
    "NetworkCode" character varying(3) NOT NULL,
    "StationCode" character varying(4) NOT NULL,
    "ReceiverCode" character varying(22) NOT NULL,
    "ReceiverSerial" character varying(22),
    "ReceiverFirmware" character varying(10),
    "AntennaCode" character varying(22) NOT NULL,
    "AntennaSerial" character varying(20),
    "AntennaHeight" numeric(6,4) DEFAULT 0 NOT NULL,
    "AntennaNorth" numeric(12,4) DEFAULT 0 NOT NULL,
    "AntennaEast" numeric(12,4) DEFAULT 0 NOT NULL,
    "HeightCode" character varying,
    "RadomeCode" character varying(7) NOT NULL,
    "DateStart" timestamp without time zone NOT NULL,
    "DateEnd" timestamp without time zone,
    "ReceiverVers" character varying(22),
    "Comments" text,
    api_id integer NOT NULL,
    antdaz numeric(4,1)
);


ALTER TABLE public.stationinfo OWNER TO gnss_data_osu;

--
-- TOC entry 277 (class 1259 OID 567449)
-- Name: stationinfo_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.stationinfo_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stationinfo_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4111 (class 0 OID 0)
-- Dependencies: 277
-- Name: stationinfo_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.stationinfo_api_id_seq OWNED BY public.stationinfo.api_id;


--
-- TOC entry 246 (class 1259 OID 87025)
-- Name: stations; Type: TABLE; Schema: public; Owner: gnss_data_osu
--

CREATE TABLE public.stations (
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
    height numeric,
    max_dist numeric,
    dome character varying(9),
    country_code character varying(3),
    marker integer,
    alias character varying(4),
    api_id integer NOT NULL
);


ALTER TABLE public.stations OWNER TO gnss_data_osu;

--
-- TOC entry 278 (class 1259 OID 567459)
-- Name: stations_api_id_seq; Type: SEQUENCE; Schema: public; Owner: gnss_data_osu
--

CREATE SEQUENCE public.stations_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stations_api_id_seq OWNER TO gnss_data_osu;

--
-- TOC entry 4112 (class 0 OID 0)
-- Dependencies: 278
-- Name: stations_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gnss_data_osu
--

ALTER SEQUENCE public.stations_api_id_seq OWNED BY public.stations.api_id;


--
-- TOC entry 3510 (class 2604 OID 567197)
-- Name: antennas api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.antennas ALTER COLUMN api_id SET DEFAULT nextval('public.antennas_api_id_seq'::regclass);


--
-- TOC entry 3511 (class 2604 OID 567207)
-- Name: apr_coords api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.apr_coords ALTER COLUMN api_id SET DEFAULT nextval('public.apr_coords_api_id_seq'::regclass);


--
-- TOC entry 3512 (class 2604 OID 567218)
-- Name: aws_sync api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.aws_sync ALTER COLUMN api_id SET DEFAULT nextval('public.aws_sync_api_id_seq'::regclass);


--
-- TOC entry 3543 (class 2604 OID 567229)
-- Name: data_source api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.data_source ALTER COLUMN api_id SET DEFAULT nextval('public.data_source_api_id_seq'::regclass);


--
-- TOC entry 3513 (class 2604 OID 567239)
-- Name: earthquakes api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.earthquakes ALTER COLUMN api_id SET DEFAULT nextval('public.earthquakes_api_id_seq'::regclass);


--
-- TOC entry 3520 (class 2604 OID 567249)
-- Name: executions api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.executions ALTER COLUMN api_id SET DEFAULT nextval('public.executions_api_id_seq'::regclass);


--
-- TOC entry 3521 (class 2604 OID 567256)
-- Name: gamit_htc api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_htc ALTER COLUMN api_id SET DEFAULT nextval('public.gamit_htc_api_id_seq'::regclass);


--
-- TOC entry 3522 (class 2604 OID 567266)
-- Name: gamit_soln api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_soln ALTER COLUMN api_id SET DEFAULT nextval('public.gamit_soln_api_id_seq'::regclass);


--
-- TOC entry 3523 (class 2604 OID 567276)
-- Name: gamit_soln_excl api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_soln_excl ALTER COLUMN api_id SET DEFAULT nextval('public.gamit_soln_excl_api_id_seq'::regclass);


--
-- TOC entry 3524 (class 2604 OID 567286)
-- Name: gamit_stats api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_stats ALTER COLUMN api_id SET DEFAULT nextval('public.gamit_stats_api_id_seq'::regclass);


--
-- TOC entry 3525 (class 2604 OID 567296)
-- Name: gamit_subnets api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_subnets ALTER COLUMN api_id SET DEFAULT nextval('public.gamit_subnets_api_id_seq'::regclass);


--
-- TOC entry 3526 (class 2604 OID 567306)
-- Name: gamit_ztd api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_ztd ALTER COLUMN api_id SET DEFAULT nextval('public.gamit_ztd_api_id_seq'::regclass);


--
-- TOC entry 3527 (class 2604 OID 567318)
-- Name: keys api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.keys ALTER COLUMN api_id SET DEFAULT nextval('public.keys_api_id_seq'::regclass);


--
-- TOC entry 3528 (class 2604 OID 567328)
-- Name: locks api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.locks ALTER COLUMN api_id SET DEFAULT nextval('public.locks_api_id_seq'::regclass);


--
-- TOC entry 3529 (class 2604 OID 567338)
-- Name: networks api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.networks ALTER COLUMN api_id SET DEFAULT nextval('public.networks_api_id_seq'::regclass);


--
-- TOC entry 3530 (class 2604 OID 567348)
-- Name: ppp_soln api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.ppp_soln ALTER COLUMN api_id SET DEFAULT nextval('public.ppp_soln_api_id_seq'::regclass);


--
-- TOC entry 3531 (class 2604 OID 567360)
-- Name: ppp_soln_excl api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.ppp_soln_excl ALTER COLUMN api_id SET DEFAULT nextval('public.ppp_soln_excl_api_id_seq'::regclass);


--
-- TOC entry 3532 (class 2604 OID 567370)
-- Name: receivers api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.receivers ALTER COLUMN api_id SET DEFAULT nextval('public.receivers_api_id_seq'::regclass);


--
-- TOC entry 3533 (class 2604 OID 567378)
-- Name: rinex api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.rinex ALTER COLUMN api_id SET DEFAULT nextval('public.rinex_api_id_seq'::regclass);


--
-- TOC entry 3534 (class 2604 OID 567392)
-- Name: rinex_sources_info api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.rinex_sources_info ALTER COLUMN api_id SET DEFAULT nextval('public.rinex_sources_info_api_id_seq'::regclass);


--
-- TOC entry 3535 (class 2604 OID 567402)
-- Name: rinex_tank_struct api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.rinex_tank_struct ALTER COLUMN api_id SET DEFAULT nextval('public.rinex_tank_struct_api_id_seq'::regclass);


--
-- TOC entry 3544 (class 2604 OID 567410)
-- Name: sources_formats api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.sources_formats ALTER COLUMN api_id SET DEFAULT nextval('public.sources_formats_api_id_seq'::regclass);


--
-- TOC entry 3547 (class 2604 OID 567420)
-- Name: sources_stations api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.sources_stations ALTER COLUMN api_id SET DEFAULT nextval('public.sources_stations_api_id_seq'::regclass);


--
-- TOC entry 3536 (class 2604 OID 567430)
-- Name: stacks api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stacks ALTER COLUMN api_id SET DEFAULT nextval('public.stacks_api_id_seq'::regclass);


--
-- TOC entry 3537 (class 2604 OID 567441)
-- Name: stationalias api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stationalias ALTER COLUMN api_id SET DEFAULT nextval('public.stationalias_api_id_seq'::regclass);


--
-- TOC entry 3541 (class 2604 OID 567450)
-- Name: stationinfo api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stationinfo ALTER COLUMN api_id SET DEFAULT nextval('public.stationinfo_api_id_seq'::regclass);


--
-- TOC entry 3542 (class 2604 OID 567460)
-- Name: stations api_id; Type: DEFAULT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stations ALTER COLUMN api_id SET DEFAULT nextval('public.stations_api_id_seq'::regclass);


--
-- TOC entry 3553 (class 2606 OID 567205)
-- Name: antennas antennas_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.antennas
    ADD CONSTRAINT antennas_api_id_key UNIQUE (api_id);


--
-- TOC entry 3555 (class 2606 OID 16605)
-- Name: antennas antennas_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.antennas
    ADD CONSTRAINT antennas_pkey PRIMARY KEY ("AntennaCode");


--
-- TOC entry 3705 (class 2606 OID 571002)
-- Name: api_campaigns api_campaigns_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_campaigns
    ADD CONSTRAINT api_campaigns_pkey PRIMARY KEY (id);


--
-- TOC entry 3708 (class 2606 OID 571010)
-- Name: api_clustertype api_clustertype_name_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_clustertype
    ADD CONSTRAINT api_clustertype_name_key UNIQUE (name);


--
-- TOC entry 3710 (class 2606 OID 571008)
-- Name: api_clustertype api_clustertype_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_clustertype
    ADD CONSTRAINT api_clustertype_pkey PRIMARY KEY (id);


--
-- TOC entry 3713 (class 2606 OID 571018)
-- Name: api_country api_country_name_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_country
    ADD CONSTRAINT api_country_name_key UNIQUE (name);


--
-- TOC entry 3715 (class 2606 OID 571016)
-- Name: api_country api_country_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_country
    ADD CONSTRAINT api_country_pkey PRIMARY KEY (id);


--
-- TOC entry 3718 (class 2606 OID 571022)
-- Name: api_country api_country_three_digits_code_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_country
    ADD CONSTRAINT api_country_three_digits_code_key UNIQUE (three_digits_code);


--
-- TOC entry 3721 (class 2606 OID 571020)
-- Name: api_country api_country_two_digits_code_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_country
    ADD CONSTRAINT api_country_two_digits_code_key UNIQUE (two_digits_code);


--
-- TOC entry 3723 (class 2606 OID 571028)
-- Name: api_endpoint api_endpoint_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_endpoint
    ADD CONSTRAINT api_endpoint_pkey PRIMARY KEY (id);


--
-- TOC entry 3830 (class 2606 OID 571334)
-- Name: api_endpointscluster_endpoints api_endpointscluster_end_endpointscluster_id_endp_bb94e051_uniq; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_endpointscluster_endpoints
    ADD CONSTRAINT api_endpointscluster_end_endpointscluster_id_endp_bb94e051_uniq UNIQUE (endpointscluster_id, endpoint_id);


--
-- TOC entry 3834 (class 2606 OID 571187)
-- Name: api_endpointscluster_endpoints api_endpointscluster_endpoints_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_endpointscluster_endpoints
    ADD CONSTRAINT api_endpointscluster_endpoints_pkey PRIMARY KEY (id);


--
-- TOC entry 3728 (class 2606 OID 571034)
-- Name: api_endpointscluster api_endpointscluster_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_endpointscluster
    ADD CONSTRAINT api_endpointscluster_pkey PRIMARY KEY (id);


--
-- TOC entry 3734 (class 2606 OID 571042)
-- Name: api_monumenttype api_monumenttype_name_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_monumenttype
    ADD CONSTRAINT api_monumenttype_name_key UNIQUE (name);


--
-- TOC entry 3736 (class 2606 OID 571040)
-- Name: api_monumenttype api_monumenttype_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_monumenttype
    ADD CONSTRAINT api_monumenttype_pkey PRIMARY KEY (id);


--
-- TOC entry 3738 (class 2606 OID 571050)
-- Name: api_person api_person_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_person
    ADD CONSTRAINT api_person_pkey PRIMARY KEY (id);


--
-- TOC entry 3742 (class 2606 OID 571058)
-- Name: api_resource api_resource_name_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_resource
    ADD CONSTRAINT api_resource_name_key UNIQUE (name);


--
-- TOC entry 3744 (class 2606 OID 571056)
-- Name: api_resource api_resource_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_resource
    ADD CONSTRAINT api_resource_pkey PRIMARY KEY (id);


--
-- TOC entry 3836 (class 2606 OID 571350)
-- Name: api_role_endpoints_clusters api_role_endpoints_clust_role_id_endpointscluster_a2b10f39_uniq; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_role_endpoints_clusters
    ADD CONSTRAINT api_role_endpoints_clust_role_id_endpointscluster_a2b10f39_uniq UNIQUE (role_id, endpointscluster_id);


--
-- TOC entry 3839 (class 2606 OID 571203)
-- Name: api_role_endpoints_clusters api_role_endpoints_clusters_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_role_endpoints_clusters
    ADD CONSTRAINT api_role_endpoints_clusters_pkey PRIMARY KEY (id);


--
-- TOC entry 3747 (class 2606 OID 571066)
-- Name: api_role api_role_name_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_role
    ADD CONSTRAINT api_role_name_key UNIQUE (name);


--
-- TOC entry 3749 (class 2606 OID 571064)
-- Name: api_role api_role_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_role
    ADD CONSTRAINT api_role_pkey PRIMARY KEY (id);


--
-- TOC entry 3752 (class 2606 OID 571072)
-- Name: api_rolepersonstation api_rolepersonstation_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_rolepersonstation
    ADD CONSTRAINT api_rolepersonstation_pkey PRIMARY KEY (id);


--
-- TOC entry 3758 (class 2606 OID 571080)
-- Name: api_stationattachedfiles api_stationattachedfiles_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationattachedfiles
    ADD CONSTRAINT api_stationattachedfiles_pkey PRIMARY KEY (id);


--
-- TOC entry 3763 (class 2606 OID 571088)
-- Name: api_stationimages api_stationimages_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationimages
    ADD CONSTRAINT api_stationimages_pkey PRIMARY KEY (id);


--
-- TOC entry 3769 (class 2606 OID 571096)
-- Name: api_stationmeta api_stationmeta_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationmeta
    ADD CONSTRAINT api_stationmeta_pkey PRIMARY KEY (id);


--
-- TOC entry 3867 (class 2606 OID 572138)
-- Name: api_stationmetagaps api_stationmetagaps_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationmetagaps
    ADD CONSTRAINT api_stationmetagaps_pkey PRIMARY KEY (id);


--
-- TOC entry 3777 (class 2606 OID 571104)
-- Name: api_stationrole api_stationrole_name_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationrole
    ADD CONSTRAINT api_stationrole_name_key UNIQUE (name);


--
-- TOC entry 3779 (class 2606 OID 571102)
-- Name: api_stationrole api_stationrole_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationrole
    ADD CONSTRAINT api_stationrole_pkey PRIMARY KEY (id);


--
-- TOC entry 3782 (class 2606 OID 571112)
-- Name: api_stationstatus api_stationstatus_name_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationstatus
    ADD CONSTRAINT api_stationstatus_name_key UNIQUE (name);


--
-- TOC entry 3784 (class 2606 OID 571110)
-- Name: api_stationstatus api_stationstatus_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationstatus
    ADD CONSTRAINT api_stationstatus_pkey PRIMARY KEY (id);


--
-- TOC entry 3787 (class 2606 OID 571120)
-- Name: api_stationtype api_stationtype_name_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationtype
    ADD CONSTRAINT api_stationtype_name_key UNIQUE (name);


--
-- TOC entry 3789 (class 2606 OID 571118)
-- Name: api_stationtype api_stationtype_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationtype
    ADD CONSTRAINT api_stationtype_pkey PRIMARY KEY (id);


--
-- TOC entry 3819 (class 2606 OID 571168)
-- Name: api_user_groups api_user_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_user_groups
    ADD CONSTRAINT api_user_groups_pkey PRIMARY KEY (id);


--
-- TOC entry 3822 (class 2606 OID 571305)
-- Name: api_user_groups api_user_groups_user_id_group_id_9c7ddfb5_uniq; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_user_groups
    ADD CONSTRAINT api_user_groups_user_id_group_id_9c7ddfb5_uniq UNIQUE (user_id, group_id);


--
-- TOC entry 3812 (class 2606 OID 571160)
-- Name: api_user api_user_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_user
    ADD CONSTRAINT api_user_pkey PRIMARY KEY (id);


--
-- TOC entry 3825 (class 2606 OID 571174)
-- Name: api_user_user_permissions api_user_user_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_user_user_permissions
    ADD CONSTRAINT api_user_user_permissions_pkey PRIMARY KEY (id);


--
-- TOC entry 3828 (class 2606 OID 571319)
-- Name: api_user_user_permissions api_user_user_permissions_user_id_permission_id_a06dd704_uniq; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_user_user_permissions
    ADD CONSTRAINT api_user_user_permissions_user_id_permission_id_a06dd704_uniq UNIQUE (user_id, permission_id);


--
-- TOC entry 3816 (class 2606 OID 571162)
-- Name: api_user api_user_username_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_user
    ADD CONSTRAINT api_user_username_key UNIQUE (username);


--
-- TOC entry 3791 (class 2606 OID 571128)
-- Name: api_visitattachedfiles api_visitattachedfiles_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visitattachedfiles
    ADD CONSTRAINT api_visitattachedfiles_pkey PRIMARY KEY (id);


--
-- TOC entry 3796 (class 2606 OID 571136)
-- Name: api_visitgnssdatafiles api_visitgnssdatafiles_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visitgnssdatafiles
    ADD CONSTRAINT api_visitgnssdatafiles_pkey PRIMARY KEY (id);


--
-- TOC entry 3801 (class 2606 OID 571144)
-- Name: api_visitimages api_visitimages_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visitimages
    ADD CONSTRAINT api_visitimages_pkey PRIMARY KEY (id);


--
-- TOC entry 3843 (class 2606 OID 571264)
-- Name: api_visits_people api_visits_people_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visits_people
    ADD CONSTRAINT api_visits_people_pkey PRIMARY KEY (id);


--
-- TOC entry 3846 (class 2606 OID 571375)
-- Name: api_visits_people api_visits_people_visits_id_person_id_4a57a25d_uniq; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visits_people
    ADD CONSTRAINT api_visits_people_visits_id_person_id_4a57a25d_uniq UNIQUE (visits_id, person_id);


--
-- TOC entry 3807 (class 2606 OID 571152)
-- Name: api_visits api_visits_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visits
    ADD CONSTRAINT api_visits_pkey PRIMARY KEY (id);


--
-- TOC entry 3557 (class 2606 OID 567216)
-- Name: apr_coords apr_coords_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.apr_coords
    ADD CONSTRAINT apr_coords_api_id_key UNIQUE (api_id);


--
-- TOC entry 3560 (class 2606 OID 16606)
-- Name: apr_coords apr_coords_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.apr_coords
    ADD CONSTRAINT apr_coords_pkey PRIMARY KEY ("NetworkCode", "StationCode", "Year", "DOY");


--
-- TOC entry 3860 (class 2606 OID 571435)
-- Name: auditlog_logentry auditlog_logentry_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.auditlog_logentry
    ADD CONSTRAINT auditlog_logentry_pkey PRIMARY KEY (id);


--
-- TOC entry 3695 (class 2606 OID 570995)
-- Name: auth_group auth_group_name_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_name_key UNIQUE (name);


--
-- TOC entry 3700 (class 2606 OID 570981)
-- Name: auth_group_permissions auth_group_permissions_group_id_permission_id_0cd325b0_uniq; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_permission_id_0cd325b0_uniq UNIQUE (group_id, permission_id);


--
-- TOC entry 3703 (class 2606 OID 570970)
-- Name: auth_group_permissions auth_group_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_pkey PRIMARY KEY (id);


--
-- TOC entry 3697 (class 2606 OID 570962)
-- Name: auth_group auth_group_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_pkey PRIMARY KEY (id);


--
-- TOC entry 3690 (class 2606 OID 570972)
-- Name: auth_permission auth_permission_content_type_id_codename_01ab375a_uniq; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_codename_01ab375a_uniq UNIQUE (content_type_id, codename);


--
-- TOC entry 3692 (class 2606 OID 570956)
-- Name: auth_permission auth_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_pkey PRIMARY KEY (id);


--
-- TOC entry 3562 (class 2606 OID 567227)
-- Name: aws_sync aws_sync_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.aws_sync
    ADD CONSTRAINT aws_sync_api_id_key UNIQUE (api_id);


--
-- TOC entry 3565 (class 2606 OID 16607)
-- Name: aws_sync aws_sync_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.aws_sync
    ADD CONSTRAINT aws_sync_pkey PRIMARY KEY ("NetworkCode", "StationCode", "Year", "DOY");


--
-- TOC entry 3669 (class 2606 OID 567237)
-- Name: data_source data_source_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.data_source
    ADD CONSTRAINT data_source_api_id_key UNIQUE (api_id);


--
-- TOC entry 3671 (class 2606 OID 16608)
-- Name: data_source data_source_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.data_source
    ADD CONSTRAINT data_source_pkey PRIMARY KEY ("NetworkCode", "StationCode", try_order);


--
-- TOC entry 3548 (class 2606 OID 16609)
-- Name: stationinfo date_chk; Type: CHECK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE public.stationinfo
    ADD CONSTRAINT date_chk CHECK (("DateEnd" > "DateStart")) NOT VALID;


--
-- TOC entry 3849 (class 2606 OID 571400)
-- Name: django_admin_log django_admin_log_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_pkey PRIMARY KEY (id);


--
-- TOC entry 3685 (class 2606 OID 570950)
-- Name: django_content_type django_content_type_app_label_model_76bd3d3b_uniq; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_app_label_model_76bd3d3b_uniq UNIQUE (app_label, model);


--
-- TOC entry 3687 (class 2606 OID 570948)
-- Name: django_content_type django_content_type_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id);


--
-- TOC entry 3683 (class 2606 OID 570942)
-- Name: django_migrations django_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.django_migrations
    ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);


--
-- TOC entry 3864 (class 2606 OID 571496)
-- Name: django_session django_session_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.django_session
    ADD CONSTRAINT django_session_pkey PRIMARY KEY (session_key);


--
-- TOC entry 3567 (class 2606 OID 567247)
-- Name: earthquakes earthquakes_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.earthquakes
    ADD CONSTRAINT earthquakes_api_id_key UNIQUE (api_id);


--
-- TOC entry 3569 (class 2606 OID 16610)
-- Name: earthquakes earthquakes_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.earthquakes
    ADD CONSTRAINT earthquakes_pkey PRIMARY KEY (date, lat, lon);


--
-- TOC entry 3572 (class 2606 OID 16611)
-- Name: etm_params etm_params_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.etm_params
    ADD CONSTRAINT etm_params_pkey PRIMARY KEY (uid);


--
-- TOC entry 3574 (class 2606 OID 16612)
-- Name: etms etmsv2_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.etms
    ADD CONSTRAINT etmsv2_pkey PRIMARY KEY (uid);


--
-- TOC entry 3577 (class 2606 OID 16613)
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (event_id, "EventDate");


--
-- TOC entry 3579 (class 2606 OID 567254)
-- Name: executions executions_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.executions
    ADD CONSTRAINT executions_api_id_key UNIQUE (api_id);


--
-- TOC entry 3581 (class 2606 OID 567264)
-- Name: gamit_htc gamit_htc_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_htc
    ADD CONSTRAINT gamit_htc_api_id_key UNIQUE (api_id);


--
-- TOC entry 3583 (class 2606 OID 16614)
-- Name: gamit_htc gamit_htc_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_htc
    ADD CONSTRAINT gamit_htc_pkey PRIMARY KEY ("AntennaCode", "HeightCode");


--
-- TOC entry 3585 (class 2606 OID 567274)
-- Name: gamit_soln gamit_soln_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_soln
    ADD CONSTRAINT gamit_soln_api_id_key UNIQUE (api_id);


--
-- TOC entry 3589 (class 2606 OID 567284)
-- Name: gamit_soln_excl gamit_soln_excl_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_soln_excl
    ADD CONSTRAINT gamit_soln_excl_api_id_key UNIQUE (api_id);


--
-- TOC entry 3591 (class 2606 OID 16615)
-- Name: gamit_soln_excl gamit_soln_excl_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_soln_excl
    ADD CONSTRAINT gamit_soln_excl_pkey PRIMARY KEY ("NetworkCode", "StationCode", "Project", "Year", "DOY");


--
-- TOC entry 3587 (class 2606 OID 16616)
-- Name: gamit_soln gamit_soln_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_soln
    ADD CONSTRAINT gamit_soln_pkey PRIMARY KEY ("NetworkCode", "StationCode", "Project", "Year", "DOY");


--
-- TOC entry 3593 (class 2606 OID 567294)
-- Name: gamit_stats gamit_stats_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_stats
    ADD CONSTRAINT gamit_stats_api_id_key UNIQUE (api_id);


--
-- TOC entry 3595 (class 2606 OID 16617)
-- Name: gamit_stats gamit_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_stats
    ADD CONSTRAINT gamit_stats_pkey PRIMARY KEY ("Project", subnet, "Year", "DOY", system);


--
-- TOC entry 3597 (class 2606 OID 567304)
-- Name: gamit_subnets gamit_subnets_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_subnets
    ADD CONSTRAINT gamit_subnets_api_id_key UNIQUE (api_id);


--
-- TOC entry 3599 (class 2606 OID 16618)
-- Name: gamit_subnets gamit_subnets_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_subnets
    ADD CONSTRAINT gamit_subnets_pkey PRIMARY KEY ("Project", subnet, "Year", "DOY");


--
-- TOC entry 3601 (class 2606 OID 567316)
-- Name: gamit_ztd gamit_ztd_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_ztd
    ADD CONSTRAINT gamit_ztd_api_id_key UNIQUE (api_id);


--
-- TOC entry 3604 (class 2606 OID 16619)
-- Name: gamit_ztd gamit_ztd_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_ztd
    ADD CONSTRAINT gamit_ztd_pkey PRIMARY KEY ("NetworkCode", "StationCode", "Date", "Project", "Year", "DOY");


--
-- TOC entry 3606 (class 2606 OID 567326)
-- Name: keys keys_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.keys
    ADD CONSTRAINT keys_api_id_key UNIQUE (api_id);


--
-- TOC entry 3608 (class 2606 OID 16620)
-- Name: keys keys_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.keys
    ADD CONSTRAINT keys_pkey PRIMARY KEY ("KeyCode");


--
-- TOC entry 3610 (class 2606 OID 567336)
-- Name: locks locks_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.locks
    ADD CONSTRAINT locks_api_id_key UNIQUE (api_id);


--
-- TOC entry 3612 (class 2606 OID 16621)
-- Name: locks locks_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.locks
    ADD CONSTRAINT locks_pkey PRIMARY KEY (filename);


--
-- TOC entry 3614 (class 2606 OID 16622)
-- Name: networks networks_NetworkCode_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.networks
    ADD CONSTRAINT "networks_NetworkCode_pkey" PRIMARY KEY ("NetworkCode");


--
-- TOC entry 3616 (class 2606 OID 567346)
-- Name: networks networks_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.networks
    ADD CONSTRAINT networks_api_id_key UNIQUE (api_id);


--
-- TOC entry 3725 (class 2606 OID 571176)
-- Name: api_endpoint path_method_unique; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_endpoint
    ADD CONSTRAINT path_method_unique UNIQUE (path, method);


--
-- TOC entry 3618 (class 2606 OID 567358)
-- Name: ppp_soln ppp_soln_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.ppp_soln
    ADD CONSTRAINT ppp_soln_api_id_key UNIQUE (api_id);


--
-- TOC entry 3624 (class 2606 OID 567368)
-- Name: ppp_soln_excl ppp_soln_excl_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.ppp_soln_excl
    ADD CONSTRAINT ppp_soln_excl_api_id_key UNIQUE (api_id);


--
-- TOC entry 3626 (class 2606 OID 16623)
-- Name: ppp_soln_excl ppp_soln_excl_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.ppp_soln_excl
    ADD CONSTRAINT ppp_soln_excl_pkey PRIMARY KEY ("NetworkCode", "StationCode", "Year", "DOY");


--
-- TOC entry 3622 (class 2606 OID 16624)
-- Name: ppp_soln ppp_soln_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.ppp_soln
    ADD CONSTRAINT ppp_soln_pkey PRIMARY KEY ("NetworkCode", "StationCode", "Year", "DOY", "ReferenceFrame");


--
-- TOC entry 3628 (class 2606 OID 16625)
-- Name: receivers receivers_ReceiverCode_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.receivers
    ADD CONSTRAINT "receivers_ReceiverCode_pkey" PRIMARY KEY ("ReceiverCode");


--
-- TOC entry 3630 (class 2606 OID 567376)
-- Name: receivers receivers_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.receivers
    ADD CONSTRAINT receivers_api_id_key UNIQUE (api_id);


--
-- TOC entry 3731 (class 2606 OID 571286)
-- Name: api_endpointscluster resource_cluster_type_role_type_description_unique; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_endpointscluster
    ADD CONSTRAINT resource_cluster_type_role_type_description_unique UNIQUE (resource_id, cluster_type_id, role_type, description);


--
-- TOC entry 3634 (class 2606 OID 567390)
-- Name: rinex rinex_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.rinex
    ADD CONSTRAINT rinex_api_id_key UNIQUE (api_id);


--
-- TOC entry 3638 (class 2606 OID 16626)
-- Name: rinex rinex_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.rinex
    ADD CONSTRAINT rinex_pkey PRIMARY KEY ("NetworkCode", "StationCode", "ObservationYear", "ObservationDOY", "Interval", "Completion");


--
-- TOC entry 3640 (class 2606 OID 567400)
-- Name: rinex_sources_info rinex_sources_info_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.rinex_sources_info
    ADD CONSTRAINT rinex_sources_info_api_id_key UNIQUE (api_id);


--
-- TOC entry 3642 (class 2606 OID 16627)
-- Name: rinex_sources_info rinex_sources_info_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.rinex_sources_info
    ADD CONSTRAINT rinex_sources_info_pkey PRIMARY KEY (name);


--
-- TOC entry 3644 (class 2606 OID 567408)
-- Name: rinex_tank_struct rinex_tank_struct_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.rinex_tank_struct
    ADD CONSTRAINT rinex_tank_struct_api_id_key UNIQUE (api_id);


--
-- TOC entry 3646 (class 2606 OID 16628)
-- Name: rinex_tank_struct rinex_tank_struct_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.rinex_tank_struct
    ADD CONSTRAINT rinex_tank_struct_pkey PRIMARY KEY ("Level");


--
-- TOC entry 3756 (class 2606 OID 571288)
-- Name: api_rolepersonstation role_person_station_unique; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_rolepersonstation
    ADD CONSTRAINT role_person_station_unique UNIQUE (role_id, person_id, station_id);


--
-- TOC entry 3673 (class 2606 OID 567418)
-- Name: sources_formats sources_formats_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.sources_formats
    ADD CONSTRAINT sources_formats_api_id_key UNIQUE (api_id);


--
-- TOC entry 3675 (class 2606 OID 16629)
-- Name: sources_formats sources_formats_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.sources_formats
    ADD CONSTRAINT sources_formats_pkey PRIMARY KEY (format);


--
-- TOC entry 3677 (class 2606 OID 16630)
-- Name: sources_servers sources_servers_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.sources_servers
    ADD CONSTRAINT sources_servers_pkey PRIMARY KEY (server_id);


--
-- TOC entry 3679 (class 2606 OID 567428)
-- Name: sources_stations sources_stations_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.sources_stations
    ADD CONSTRAINT sources_stations_api_id_key UNIQUE (api_id);


--
-- TOC entry 3681 (class 2606 OID 16631)
-- Name: sources_stations sources_stations_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.sources_stations
    ADD CONSTRAINT sources_stations_pkey PRIMARY KEY ("NetworkCode", "StationCode", try_order);


--
-- TOC entry 3648 (class 2606 OID 567439)
-- Name: stacks stacks_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stacks
    ADD CONSTRAINT stacks_api_id_key UNIQUE (api_id);


--
-- TOC entry 3651 (class 2606 OID 16632)
-- Name: stacks stacks_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stacks
    ADD CONSTRAINT stacks_pkey PRIMARY KEY ("NetworkCode", "StationCode", "Year", "DOY", name);


--
-- TOC entry 3810 (class 2606 OID 571292)
-- Name: api_visits station_date_unique; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visits
    ADD CONSTRAINT station_date_unique UNIQUE (station_id, date);


--
-- TOC entry 3761 (class 2606 OID 643684)
-- Name: api_stationattachedfiles station_filename_unique; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationattachedfiles
    ADD CONSTRAINT station_filename_unique UNIQUE (station_id, filename);


--
-- TOC entry 3766 (class 2606 OID 643686)
-- Name: api_stationimages station_name_unique; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationimages
    ADD CONSTRAINT station_name_unique UNIQUE (station_id, name);


--
-- TOC entry 3774 (class 2606 OID 571290)
-- Name: api_stationmeta station_unique; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationmeta
    ADD CONSTRAINT station_unique UNIQUE (station_id);


--
-- TOC entry 3653 (class 2606 OID 567448)
-- Name: stationalias stationalias_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stationalias
    ADD CONSTRAINT stationalias_api_id_key UNIQUE (api_id);


--
-- TOC entry 3655 (class 2606 OID 16633)
-- Name: stationalias stationalias_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stationalias
    ADD CONSTRAINT stationalias_pkey PRIMARY KEY ("NetworkCode", "StationCode");


--
-- TOC entry 3657 (class 2606 OID 16634)
-- Name: stationalias stationalias_uniq; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stationalias
    ADD CONSTRAINT stationalias_uniq UNIQUE ("StationAlias");


--
-- TOC entry 3659 (class 2606 OID 16635)
-- Name: stationinfo stationinfo_NetworkCode_StationCode_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stationinfo
    ADD CONSTRAINT "stationinfo_NetworkCode_StationCode_pkey" PRIMARY KEY ("NetworkCode", "StationCode", "DateStart");


--
-- TOC entry 3661 (class 2606 OID 567458)
-- Name: stationinfo stationinfo_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stationinfo
    ADD CONSTRAINT stationinfo_api_id_key UNIQUE (api_id);


--
-- TOC entry 3664 (class 2606 OID 16636)
-- Name: stations stations_NetworkCode_StationCode_pkey; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stations
    ADD CONSTRAINT "stations_NetworkCode_StationCode_pkey" PRIMARY KEY ("NetworkCode", "StationCode");


--
-- TOC entry 3666 (class 2606 OID 567469)
-- Name: stations stations_api_id_key; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stations
    ADD CONSTRAINT stations_api_id_key UNIQUE (api_id);


--
-- TOC entry 3799 (class 2606 OID 643690)
-- Name: api_visitgnssdatafiles visit_filename_gnss_unique; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visitgnssdatafiles
    ADD CONSTRAINT visit_filename_gnss_unique UNIQUE (visit_id, filename);


--
-- TOC entry 3794 (class 2606 OID 643688)
-- Name: api_visitattachedfiles visit_filename_unique; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visitattachedfiles
    ADD CONSTRAINT visit_filename_unique UNIQUE (visit_id, filename);


--
-- TOC entry 3804 (class 2606 OID 643682)
-- Name: api_visitimages visit_name_unique; Type: CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visitimages
    ADD CONSTRAINT visit_name_unique UNIQUE (visit_id, name);


--
-- TOC entry 3631 (class 1259 OID 522536)
-- Name: Filename; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX "Filename" ON public.rinex USING btree ("Filename" varchar_ops);


--
-- TOC entry 3706 (class 1259 OID 571293)
-- Name: api_clustertype_name_95bb2535_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_clustertype_name_95bb2535_like ON public.api_clustertype USING btree (name varchar_pattern_ops);


--
-- TOC entry 3711 (class 1259 OID 571294)
-- Name: api_country_name_6a70666f_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_country_name_6a70666f_like ON public.api_country USING btree (name varchar_pattern_ops);


--
-- TOC entry 3716 (class 1259 OID 571296)
-- Name: api_country_three_digits_code_b42e8ca2_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_country_three_digits_code_b42e8ca2_like ON public.api_country USING btree (three_digits_code varchar_pattern_ops);


--
-- TOC entry 3719 (class 1259 OID 571295)
-- Name: api_country_two_digits_code_08ee4eef_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_country_two_digits_code_08ee4eef_like ON public.api_country USING btree (two_digits_code varchar_pattern_ops);


--
-- TOC entry 3726 (class 1259 OID 571332)
-- Name: api_endpointscluster_cluster_type_id_1e49af86; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_endpointscluster_cluster_type_id_1e49af86 ON public.api_endpointscluster USING btree (cluster_type_id);


--
-- TOC entry 3831 (class 1259 OID 571346)
-- Name: api_endpointscluster_endpoints_endpoint_id_6657e51f; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_endpointscluster_endpoints_endpoint_id_6657e51f ON public.api_endpointscluster_endpoints USING btree (endpoint_id);


--
-- TOC entry 3832 (class 1259 OID 571345)
-- Name: api_endpointscluster_endpoints_endpointscluster_id_9d81b5e9; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_endpointscluster_endpoints_endpointscluster_id_9d81b5e9 ON public.api_endpointscluster_endpoints USING btree (endpointscluster_id);


--
-- TOC entry 3729 (class 1259 OID 571348)
-- Name: api_endpointscluster_resource_id_5bd92927; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_endpointscluster_resource_id_5bd92927 ON public.api_endpointscluster USING btree (resource_id);


--
-- TOC entry 3732 (class 1259 OID 571297)
-- Name: api_monumenttype_name_b69135a7_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_monumenttype_name_b69135a7_like ON public.api_monumenttype USING btree (name varchar_pattern_ops);


--
-- TOC entry 3739 (class 1259 OID 571347)
-- Name: api_person_user_id_c3411bd2; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_person_user_id_c3411bd2 ON public.api_person USING btree (user_id);


--
-- TOC entry 3740 (class 1259 OID 571298)
-- Name: api_resource_name_ffa965d2_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_resource_name_ffa965d2_like ON public.api_resource USING btree (name varchar_pattern_ops);


--
-- TOC entry 3837 (class 1259 OID 571362)
-- Name: api_role_endpoints_clusters_endpointscluster_id_755b18d0; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_role_endpoints_clusters_endpointscluster_id_755b18d0 ON public.api_role_endpoints_clusters USING btree (endpointscluster_id);


--
-- TOC entry 3840 (class 1259 OID 571361)
-- Name: api_role_endpoints_clusters_role_id_49c77584; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_role_endpoints_clusters_role_id_49c77584 ON public.api_role_endpoints_clusters USING btree (role_id);


--
-- TOC entry 3745 (class 1259 OID 571299)
-- Name: api_role_name_b5227b52_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_role_name_b5227b52_like ON public.api_role USING btree (name varchar_pattern_ops);


--
-- TOC entry 3750 (class 1259 OID 571364)
-- Name: api_rolepersonstation_person_id_0221bab2; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_rolepersonstation_person_id_0221bab2 ON public.api_rolepersonstation USING btree (person_id);


--
-- TOC entry 3753 (class 1259 OID 571370)
-- Name: api_rolepersonstation_role_id_b85fba4f; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_rolepersonstation_role_id_b85fba4f ON public.api_rolepersonstation USING btree (role_id);


--
-- TOC entry 3754 (class 1259 OID 571365)
-- Name: api_rolepersonstation_station_id_19834f7f; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_rolepersonstation_station_id_19834f7f ON public.api_rolepersonstation USING btree (station_id);


--
-- TOC entry 3759 (class 1259 OID 571366)
-- Name: api_stationattachedfiles_station_id_c8c09298; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_stationattachedfiles_station_id_c8c09298 ON public.api_stationattachedfiles USING btree (station_id);


--
-- TOC entry 3764 (class 1259 OID 571367)
-- Name: api_stationimages_station_id_af6b1a21; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_stationimages_station_id_af6b1a21 ON public.api_stationimages USING btree (station_id);


--
-- TOC entry 3767 (class 1259 OID 571368)
-- Name: api_stationmeta_monument_type_id_763f1881; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_stationmeta_monument_type_id_763f1881 ON public.api_stationmeta USING btree (monument_type_id);


--
-- TOC entry 3770 (class 1259 OID 571369)
-- Name: api_stationmeta_station_id_6a9e6239; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_stationmeta_station_id_6a9e6239 ON public.api_stationmeta USING btree (station_id);


--
-- TOC entry 3771 (class 1259 OID 571372)
-- Name: api_stationmeta_station_type_id_11f0671d; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_stationmeta_station_type_id_11f0671d ON public.api_stationmeta USING btree (station_type_id);


--
-- TOC entry 3772 (class 1259 OID 571371)
-- Name: api_stationmeta_status_id_7e2c16db; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_stationmeta_status_id_7e2c16db ON public.api_stationmeta USING btree (status_id);


--
-- TOC entry 3868 (class 1259 OID 572144)
-- Name: api_stationmetagaps_station_meta_id_654c7394; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_stationmetagaps_station_meta_id_654c7394 ON public.api_stationmetagaps USING btree (station_meta_id);


--
-- TOC entry 3775 (class 1259 OID 571300)
-- Name: api_stationrole_name_efed581e_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_stationrole_name_efed581e_like ON public.api_stationrole USING btree (name varchar_pattern_ops);


--
-- TOC entry 3780 (class 1259 OID 571301)
-- Name: api_stationstatus_name_9c4e75bd_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_stationstatus_name_9c4e75bd_like ON public.api_stationstatus USING btree (name varchar_pattern_ops);


--
-- TOC entry 3785 (class 1259 OID 571302)
-- Name: api_stationtype_name_07a83d18_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_stationtype_name_07a83d18_like ON public.api_stationtype USING btree (name varchar_pattern_ops);


--
-- TOC entry 3817 (class 1259 OID 571317)
-- Name: api_user_groups_group_id_3af85785; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_user_groups_group_id_3af85785 ON public.api_user_groups USING btree (group_id);


--
-- TOC entry 3820 (class 1259 OID 571316)
-- Name: api_user_groups_user_id_a5ff39fa; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_user_groups_user_id_a5ff39fa ON public.api_user_groups USING btree (user_id);


--
-- TOC entry 3813 (class 1259 OID 571363)
-- Name: api_user_role_id_0b60389b; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_user_role_id_0b60389b ON public.api_user USING btree (role_id);


--
-- TOC entry 3823 (class 1259 OID 571331)
-- Name: api_user_user_permissions_permission_id_305b7fea; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_user_user_permissions_permission_id_305b7fea ON public.api_user_user_permissions USING btree (permission_id);


--
-- TOC entry 3826 (class 1259 OID 571330)
-- Name: api_user_user_permissions_user_id_f3945d65; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_user_user_permissions_user_id_f3945d65 ON public.api_user_user_permissions USING btree (user_id);


--
-- TOC entry 3814 (class 1259 OID 571303)
-- Name: api_user_username_cf4e88d2_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_user_username_cf4e88d2_like ON public.api_user USING btree (username varchar_pattern_ops);


--
-- TOC entry 3792 (class 1259 OID 571391)
-- Name: api_visitattachedfiles_visit_id_78032a67; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_visitattachedfiles_visit_id_78032a67 ON public.api_visitattachedfiles USING btree (visit_id);


--
-- TOC entry 3797 (class 1259 OID 571390)
-- Name: api_visitgnssdatafiles_visit_id_d1beb947; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_visitgnssdatafiles_visit_id_d1beb947 ON public.api_visitgnssdatafiles USING btree (visit_id);


--
-- TOC entry 3802 (class 1259 OID 571389)
-- Name: api_visitimages_visit_id_86ae72e5; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_visitimages_visit_id_86ae72e5 ON public.api_visitimages USING btree (visit_id);


--
-- TOC entry 3805 (class 1259 OID 571373)
-- Name: api_visits_campaign_id_a7379fb8; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_visits_campaign_id_a7379fb8 ON public.api_visits USING btree (campaign_id);


--
-- TOC entry 3841 (class 1259 OID 571387)
-- Name: api_visits_people_person_id_ffe688b6; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_visits_people_person_id_ffe688b6 ON public.api_visits_people USING btree (person_id);


--
-- TOC entry 3844 (class 1259 OID 571386)
-- Name: api_visits_people_visits_id_69447804; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_visits_people_visits_id_69447804 ON public.api_visits_people USING btree (visits_id);


--
-- TOC entry 3808 (class 1259 OID 571388)
-- Name: api_visits_station_id_5179987a; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX api_visits_station_id_5179987a ON public.api_visits USING btree (station_id);


--
-- TOC entry 3558 (class 1259 OID 522537)
-- Name: apr_coords_date_idx; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX apr_coords_date_idx ON public.apr_coords USING btree ("NetworkCode", "StationCode", "Year", "DOY");


--
-- TOC entry 3851 (class 1259 OID 571470)
-- Name: auditlog_logentry_action_229afe39; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX auditlog_logentry_action_229afe39 ON public.auditlog_logentry USING btree (action);


--
-- TOC entry 3852 (class 1259 OID 571447)
-- Name: auditlog_logentry_actor_id_959271d2; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX auditlog_logentry_actor_id_959271d2 ON public.auditlog_logentry USING btree (actor_id);


--
-- TOC entry 3853 (class 1259 OID 571472)
-- Name: auditlog_logentry_cid_9f467263; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX auditlog_logentry_cid_9f467263 ON public.auditlog_logentry USING btree (cid);


--
-- TOC entry 3854 (class 1259 OID 571473)
-- Name: auditlog_logentry_cid_9f467263_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX auditlog_logentry_cid_9f467263_like ON public.auditlog_logentry USING btree (cid varchar_pattern_ops);


--
-- TOC entry 3855 (class 1259 OID 571448)
-- Name: auditlog_logentry_content_type_id_75830218; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX auditlog_logentry_content_type_id_75830218 ON public.auditlog_logentry USING btree (content_type_id);


--
-- TOC entry 3856 (class 1259 OID 571449)
-- Name: auditlog_logentry_object_id_09c2eee8; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX auditlog_logentry_object_id_09c2eee8 ON public.auditlog_logentry USING btree (object_id);


--
-- TOC entry 3857 (class 1259 OID 571468)
-- Name: auditlog_logentry_object_pk_6e3219c0; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX auditlog_logentry_object_pk_6e3219c0 ON public.auditlog_logentry USING btree (object_pk);


--
-- TOC entry 3858 (class 1259 OID 571469)
-- Name: auditlog_logentry_object_pk_6e3219c0_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX auditlog_logentry_object_pk_6e3219c0_like ON public.auditlog_logentry USING btree (object_pk varchar_pattern_ops);


--
-- TOC entry 3861 (class 1259 OID 571471)
-- Name: auditlog_logentry_timestamp_37867bb0; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX auditlog_logentry_timestamp_37867bb0 ON public.auditlog_logentry USING btree ("timestamp");


--
-- TOC entry 3693 (class 1259 OID 570996)
-- Name: auth_group_name_a6ea08ec_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX auth_group_name_a6ea08ec_like ON public.auth_group USING btree (name varchar_pattern_ops);


--
-- TOC entry 3698 (class 1259 OID 570992)
-- Name: auth_group_permissions_group_id_b120cbf9; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX auth_group_permissions_group_id_b120cbf9 ON public.auth_group_permissions USING btree (group_id);


--
-- TOC entry 3701 (class 1259 OID 570993)
-- Name: auth_group_permissions_permission_id_84c5c92e; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX auth_group_permissions_permission_id_84c5c92e ON public.auth_group_permissions USING btree (permission_id);


--
-- TOC entry 3688 (class 1259 OID 570978)
-- Name: auth_permission_content_type_id_2f476e4b; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX auth_permission_content_type_id_2f476e4b ON public.auth_permission USING btree (content_type_id);


--
-- TOC entry 3563 (class 1259 OID 522538)
-- Name: aws_sync_idx; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX aws_sync_idx ON public.aws_sync USING btree ("NetworkCode", "StationCode", "StationAlias", "Year", "DOY");


--
-- TOC entry 3847 (class 1259 OID 571411)
-- Name: django_admin_log_content_type_id_c4bce8eb; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX django_admin_log_content_type_id_c4bce8eb ON public.django_admin_log USING btree (content_type_id);


--
-- TOC entry 3850 (class 1259 OID 571412)
-- Name: django_admin_log_user_id_c564eba6; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX django_admin_log_user_id_c564eba6 ON public.django_admin_log USING btree (user_id);


--
-- TOC entry 3862 (class 1259 OID 571498)
-- Name: django_session_expire_date_a5c62663; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX django_session_expire_date_a5c62663 ON public.django_session USING btree (expire_date);


--
-- TOC entry 3865 (class 1259 OID 571497)
-- Name: django_session_session_key_c0390e0f_like; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX django_session_session_key_c0390e0f_like ON public.django_session USING btree (session_key varchar_pattern_ops);


--
-- TOC entry 3570 (class 1259 OID 522539)
-- Name: etm_params_idx; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX etm_params_idx ON public.etm_params USING btree ("NetworkCode", "StationCode", soln, object);


--
-- TOC entry 3575 (class 1259 OID 522540)
-- Name: events_index; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX events_index ON public.events USING btree ("NetworkCode", "StationCode", "Year", "DOY");


--
-- TOC entry 3602 (class 1259 OID 522541)
-- Name: gamit_ztd_idx; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX gamit_ztd_idx ON public.gamit_ztd USING btree ("Project", "Year", "DOY");


--
-- TOC entry 3632 (class 1259 OID 522542)
-- Name: network_station; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX network_station ON public.rinex USING btree ("NetworkCode" varchar_ops, "StationCode" varchar_ops);


--
-- TOC entry 3619 (class 1259 OID 522543)
-- Name: ppp_soln_idx; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX ppp_soln_idx ON public.ppp_soln USING btree ("NetworkCode" COLLATE "C" varchar_ops, "StationCode" COLLATE "C" varchar_ops);


--
-- TOC entry 3620 (class 1259 OID 522544)
-- Name: ppp_soln_order; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX ppp_soln_order ON public.ppp_soln USING btree ("NetworkCode", "StationCode", "Year", "DOY");


--
-- TOC entry 3635 (class 1259 OID 522545)
-- Name: rinex_obs_comp_idx; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX rinex_obs_comp_idx ON public.rinex USING btree ("NetworkCode", "StationCode", "ObservationYear", "ObservationDOY", "Completion");


--
-- TOC entry 3636 (class 1259 OID 522546)
-- Name: rinex_obs_idx; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX rinex_obs_idx ON public.rinex USING btree ("NetworkCode", "StationCode", "ObservationYear", "ObservationDOY");


--
-- TOC entry 3649 (class 1259 OID 522547)
-- Name: stacks_idx; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX stacks_idx ON public.stacks USING btree ("Year", "DOY");


--
-- TOC entry 3662 (class 1259 OID 522548)
-- Name: stations_NetworkCode_StationCode_idx; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE UNIQUE INDEX "stations_NetworkCode_StationCode_idx" ON public.stations USING btree ("NetworkCode", "StationCode");


--
-- TOC entry 3667 (class 1259 OID 567932)
-- Name: stations_country_code_idx; Type: INDEX; Schema: public; Owner: gnss_data_osu
--

CREATE INDEX stations_country_code_idx ON public.stations USING btree (country_code);


--
-- TOC entry 3930 (class 2620 OID 571415)
-- Name: rinex update_has_gaps_update_needed_field_trigger; Type: TRIGGER; Schema: public; Owner: gnss_data_osu
--

CREATE TRIGGER update_has_gaps_update_needed_field_trigger AFTER INSERT OR DELETE OR UPDATE ON public.rinex FOR EACH ROW EXECUTE FUNCTION public.update_has_gaps_update_needed_field();


--
-- TOC entry 3933 (class 2620 OID 571416)
-- Name: stationinfo update_has_gaps_update_needed_field_trigger; Type: TRIGGER; Schema: public; Owner: gnss_data_osu
--

CREATE TRIGGER update_has_gaps_update_needed_field_trigger AFTER INSERT OR DELETE OR UPDATE ON public.stationinfo FOR EACH ROW EXECUTE FUNCTION public.update_has_gaps_update_needed_field();


--
-- TOC entry 3934 (class 2620 OID 571418)
-- Name: stationinfo update_has_stationinfo_field_trigger; Type: TRIGGER; Schema: public; Owner: gnss_data_osu
--

CREATE TRIGGER update_has_stationinfo_field_trigger AFTER INSERT OR DELETE OR UPDATE ON public.stationinfo FOR EACH ROW EXECUTE FUNCTION public.update_has_stationinfo_field();


--
-- TOC entry 3935 (class 2620 OID 571420)
-- Name: stations update_has_stationinfo_field_trigger; Type: TRIGGER; Schema: public; Owner: gnss_data_osu
--

CREATE TRIGGER update_has_stationinfo_field_trigger BEFORE DELETE ON public.stations FOR EACH ROW EXECUTE FUNCTION public.delete_rows_referencing_stations();


--
-- TOC entry 3931 (class 2620 OID 16637)
-- Name: rinex update_stations; Type: TRIGGER; Schema: public; Owner: gnss_data_osu
--

CREATE TRIGGER update_stations AFTER INSERT ON public.rinex FOR EACH ROW EXECUTE FUNCTION public.update_timespan_trigg();


--
-- TOC entry 3932 (class 2620 OID 16638)
-- Name: stationalias verify_stationalias; Type: TRIGGER; Schema: public; Owner: gnss_data_osu
--

CREATE TRIGGER verify_stationalias BEFORE INSERT OR UPDATE ON public.stationalias FOR EACH ROW EXECUTE FUNCTION public.stationalias_check();


--
-- TOC entry 3887 (class 2606 OID 16639)
-- Name: stations NetworkCode; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stations
    ADD CONSTRAINT "NetworkCode" FOREIGN KEY ("NetworkCode") REFERENCES public.networks("NetworkCode") MATCH FULL ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 3872 (class 2606 OID 16644)
-- Name: gamit_htc antenna_fk; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_htc
    ADD CONSTRAINT antenna_fk FOREIGN KEY ("AntennaCode") REFERENCES public.antennas("AntennaCode") ON UPDATE CASCADE ON DELETE CASCADE;


--
-- TOC entry 3897 (class 2606 OID 571177)
-- Name: api_endpointscluster api_endpointscluster_cluster_type_id_1e49af86_fk_api_clust; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_endpointscluster
    ADD CONSTRAINT api_endpointscluster_cluster_type_id_1e49af86_fk_api_clust FOREIGN KEY (cluster_type_id) REFERENCES public.api_clustertype(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3919 (class 2606 OID 571340)
-- Name: api_endpointscluster_endpoints api_endpointscluster_endpoint_id_6657e51f_fk_api_endpo; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_endpointscluster_endpoints
    ADD CONSTRAINT api_endpointscluster_endpoint_id_6657e51f_fk_api_endpo FOREIGN KEY (endpoint_id) REFERENCES public.api_endpoint(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3920 (class 2606 OID 571335)
-- Name: api_endpointscluster_endpoints api_endpointscluster_endpointscluster_id_9d81b5e9_fk_api_endpo; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_endpointscluster_endpoints
    ADD CONSTRAINT api_endpointscluster_endpointscluster_id_9d81b5e9_fk_api_endpo FOREIGN KEY (endpointscluster_id) REFERENCES public.api_endpointscluster(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3898 (class 2606 OID 571193)
-- Name: api_endpointscluster api_endpointscluster_resource_id_5bd92927_fk_api_resource_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_endpointscluster
    ADD CONSTRAINT api_endpointscluster_resource_id_5bd92927_fk_api_resource_id FOREIGN KEY (resource_id) REFERENCES public.api_resource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3899 (class 2606 OID 571188)
-- Name: api_person api_person_user_id_c3411bd2_fk_api_user_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_person
    ADD CONSTRAINT api_person_user_id_c3411bd2_fk_api_user_id FOREIGN KEY (user_id) REFERENCES public.api_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3921 (class 2606 OID 571356)
-- Name: api_role_endpoints_clusters api_role_endpoints_c_endpointscluster_id_755b18d0_fk_api_endpo; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_role_endpoints_clusters
    ADD CONSTRAINT api_role_endpoints_c_endpointscluster_id_755b18d0_fk_api_endpo FOREIGN KEY (endpointscluster_id) REFERENCES public.api_endpointscluster(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3922 (class 2606 OID 571351)
-- Name: api_role_endpoints_clusters api_role_endpoints_clusters_role_id_49c77584_fk_api_role_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_role_endpoints_clusters
    ADD CONSTRAINT api_role_endpoints_clusters_role_id_49c77584_fk_api_role_id FOREIGN KEY (role_id) REFERENCES public.api_role(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3900 (class 2606 OID 571209)
-- Name: api_rolepersonstation api_rolepersonstation_person_id_0221bab2_fk_api_person_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_rolepersonstation
    ADD CONSTRAINT api_rolepersonstation_person_id_0221bab2_fk_api_person_id FOREIGN KEY (person_id) REFERENCES public.api_person(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3901 (class 2606 OID 571239)
-- Name: api_rolepersonstation api_rolepersonstation_role_id_b85fba4f_fk_api_stationrole_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_rolepersonstation
    ADD CONSTRAINT api_rolepersonstation_role_id_b85fba4f_fk_api_stationrole_id FOREIGN KEY (role_id) REFERENCES public.api_stationrole(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3902 (class 2606 OID 571214)
-- Name: api_rolepersonstation api_rolepersonstation_station_id_19834f7f_fk_stations_api_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_rolepersonstation
    ADD CONSTRAINT api_rolepersonstation_station_id_19834f7f_fk_stations_api_id FOREIGN KEY (station_id) REFERENCES public.stations(api_id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3903 (class 2606 OID 571219)
-- Name: api_stationattachedfiles api_stationattachedfiles_station_id_c8c09298_fk_stations_api_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationattachedfiles
    ADD CONSTRAINT api_stationattachedfiles_station_id_c8c09298_fk_stations_api_id FOREIGN KEY (station_id) REFERENCES public.stations(api_id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3904 (class 2606 OID 571224)
-- Name: api_stationimages api_stationimages_station_id_af6b1a21_fk_stations_api_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationimages
    ADD CONSTRAINT api_stationimages_station_id_af6b1a21_fk_stations_api_id FOREIGN KEY (station_id) REFERENCES public.stations(api_id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3905 (class 2606 OID 571229)
-- Name: api_stationmeta api_stationmeta_monument_type_id_763f1881_fk_api_monum; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationmeta
    ADD CONSTRAINT api_stationmeta_monument_type_id_763f1881_fk_api_monum FOREIGN KEY (monument_type_id) REFERENCES public.api_monumenttype(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3906 (class 2606 OID 571234)
-- Name: api_stationmeta api_stationmeta_station_id_6a9e6239_fk_stations_api_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationmeta
    ADD CONSTRAINT api_stationmeta_station_id_6a9e6239_fk_stations_api_id FOREIGN KEY (station_id) REFERENCES public.stations(api_id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3907 (class 2606 OID 571249)
-- Name: api_stationmeta api_stationmeta_station_type_id_11f0671d_fk_api_stationtype_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationmeta
    ADD CONSTRAINT api_stationmeta_station_type_id_11f0671d_fk_api_stationtype_id FOREIGN KEY (station_type_id) REFERENCES public.api_stationtype(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3908 (class 2606 OID 571244)
-- Name: api_stationmeta api_stationmeta_status_id_7e2c16db_fk_api_stationstatus_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationmeta
    ADD CONSTRAINT api_stationmeta_status_id_7e2c16db_fk_api_stationstatus_id FOREIGN KEY (status_id) REFERENCES public.api_stationstatus(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3929 (class 2606 OID 572139)
-- Name: api_stationmetagaps api_stationmetagaps_station_meta_id_654c7394_fk_api_stati; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_stationmetagaps
    ADD CONSTRAINT api_stationmetagaps_station_meta_id_654c7394_fk_api_stati FOREIGN KEY (station_meta_id) REFERENCES public.api_stationmeta(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3915 (class 2606 OID 571311)
-- Name: api_user_groups api_user_groups_group_id_3af85785_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_user_groups
    ADD CONSTRAINT api_user_groups_group_id_3af85785_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3916 (class 2606 OID 571306)
-- Name: api_user_groups api_user_groups_user_id_a5ff39fa_fk_api_user_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_user_groups
    ADD CONSTRAINT api_user_groups_user_id_a5ff39fa_fk_api_user_id FOREIGN KEY (user_id) REFERENCES public.api_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3914 (class 2606 OID 571204)
-- Name: api_user api_user_role_id_0b60389b_fk_api_role_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_user
    ADD CONSTRAINT api_user_role_id_0b60389b_fk_api_role_id FOREIGN KEY (role_id) REFERENCES public.api_role(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3917 (class 2606 OID 571325)
-- Name: api_user_user_permissions api_user_user_permis_permission_id_305b7fea_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_user_user_permissions
    ADD CONSTRAINT api_user_user_permis_permission_id_305b7fea_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3918 (class 2606 OID 571320)
-- Name: api_user_user_permissions api_user_user_permissions_user_id_f3945d65_fk_api_user_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_user_user_permissions
    ADD CONSTRAINT api_user_user_permissions_user_id_f3945d65_fk_api_user_id FOREIGN KEY (user_id) REFERENCES public.api_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3909 (class 2606 OID 571280)
-- Name: api_visitattachedfiles api_visitattachedfiles_visit_id_78032a67_fk_api_visits_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visitattachedfiles
    ADD CONSTRAINT api_visitattachedfiles_visit_id_78032a67_fk_api_visits_id FOREIGN KEY (visit_id) REFERENCES public.api_visits(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3910 (class 2606 OID 571275)
-- Name: api_visitgnssdatafiles api_visitgnssdatafiles_visit_id_d1beb947_fk_api_visits_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visitgnssdatafiles
    ADD CONSTRAINT api_visitgnssdatafiles_visit_id_d1beb947_fk_api_visits_id FOREIGN KEY (visit_id) REFERENCES public.api_visits(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3911 (class 2606 OID 571270)
-- Name: api_visitimages api_visitimages_visit_id_86ae72e5_fk_api_visits_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visitimages
    ADD CONSTRAINT api_visitimages_visit_id_86ae72e5_fk_api_visits_id FOREIGN KEY (visit_id) REFERENCES public.api_visits(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3912 (class 2606 OID 571254)
-- Name: api_visits api_visits_campaign_id_a7379fb8_fk_api_campaigns_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visits
    ADD CONSTRAINT api_visits_campaign_id_a7379fb8_fk_api_campaigns_id FOREIGN KEY (campaign_id) REFERENCES public.api_campaigns(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3923 (class 2606 OID 571381)
-- Name: api_visits_people api_visits_people_person_id_ffe688b6_fk_api_person_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visits_people
    ADD CONSTRAINT api_visits_people_person_id_ffe688b6_fk_api_person_id FOREIGN KEY (person_id) REFERENCES public.api_person(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3924 (class 2606 OID 571376)
-- Name: api_visits_people api_visits_people_visits_id_69447804_fk_api_visits_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visits_people
    ADD CONSTRAINT api_visits_people_visits_id_69447804_fk_api_visits_id FOREIGN KEY (visits_id) REFERENCES public.api_visits(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3913 (class 2606 OID 571265)
-- Name: api_visits api_visits_station_id_5179987a_fk_stations_api_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.api_visits
    ADD CONSTRAINT api_visits_station_id_5179987a_fk_stations_api_id FOREIGN KEY (station_id) REFERENCES public.stations(api_id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3869 (class 2606 OID 16649)
-- Name: apr_coords apr_coords_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.apr_coords
    ADD CONSTRAINT "apr_coords_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES public.stations("NetworkCode", "StationCode");


--
-- TOC entry 3927 (class 2606 OID 571436)
-- Name: auditlog_logentry auditlog_logentry_actor_id_959271d2_fk_api_user_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.auditlog_logentry
    ADD CONSTRAINT auditlog_logentry_actor_id_959271d2_fk_api_user_id FOREIGN KEY (actor_id) REFERENCES public.api_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3928 (class 2606 OID 571441)
-- Name: auditlog_logentry auditlog_logentry_content_type_id_75830218_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.auditlog_logentry
    ADD CONSTRAINT auditlog_logentry_content_type_id_75830218_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3895 (class 2606 OID 570987)
-- Name: auth_group_permissions auth_group_permissio_permission_id_84c5c92e_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissio_permission_id_84c5c92e_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3896 (class 2606 OID 570982)
-- Name: auth_group_permissions auth_group_permissions_group_id_b120cbf9_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_b120cbf9_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3894 (class 2606 OID 570973)
-- Name: auth_permission auth_permission_content_type_id_2f476e4b_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_2f476e4b_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3889 (class 2606 OID 16654)
-- Name: data_source data_source_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.data_source
    ADD CONSTRAINT "data_source_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES public.stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 3925 (class 2606 OID 571401)
-- Name: django_admin_log django_admin_log_content_type_id_c4bce8eb_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_content_type_id_c4bce8eb_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3926 (class 2606 OID 571406)
-- Name: django_admin_log django_admin_log_user_id_c564eba6_fk_api_user_id; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_user_id_c564eba6_fk_api_user_id FOREIGN KEY (user_id) REFERENCES public.api_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 3871 (class 2606 OID 16659)
-- Name: etms etms_fk; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.etms
    ADD CONSTRAINT etms_fk FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES public.stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 3888 (class 2606 OID 571421)
-- Name: stations fk_country_code; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stations
    ADD CONSTRAINT fk_country_code FOREIGN KEY (country_code) REFERENCES public.api_country(three_digits_code);


--
-- TOC entry 3873 (class 2606 OID 16664)
-- Name: gamit_soln gamit_soln_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_soln
    ADD CONSTRAINT "gamit_soln_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES public.stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 3874 (class 2606 OID 16669)
-- Name: gamit_soln_excl gamit_soln_excl_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_soln_excl
    ADD CONSTRAINT "gamit_soln_excl_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode", "Project", "Year", "DOY") REFERENCES public.gamit_soln("NetworkCode", "StationCode", "Project", "Year", "DOY") ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;


--
-- TOC entry 3875 (class 2606 OID 16674)
-- Name: gamit_ztd gamit_ztd_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.gamit_ztd
    ADD CONSTRAINT "gamit_ztd_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES public.stations("NetworkCode", "StationCode");


--
-- TOC entry 3876 (class 2606 OID 16679)
-- Name: locks locks_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.locks
    ADD CONSTRAINT "locks_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES public.stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE CASCADE;


--
-- TOC entry 3877 (class 2606 OID 16684)
-- Name: ppp_soln ppp_soln_NetworkName_StationCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.ppp_soln
    ADD CONSTRAINT "ppp_soln_NetworkName_StationCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES public.stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 3878 (class 2606 OID 16689)
-- Name: ppp_soln_excl ppp_soln_excl_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.ppp_soln_excl
    ADD CONSTRAINT "ppp_soln_excl_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES public.stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 3879 (class 2606 OID 16694)
-- Name: rinex rinex_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.rinex
    ADD CONSTRAINT "rinex_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES public.stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 3880 (class 2606 OID 16699)
-- Name: rinex_tank_struct rinex_tank_struct_key_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.rinex_tank_struct
    ADD CONSTRAINT rinex_tank_struct_key_fkey FOREIGN KEY ("KeyCode") REFERENCES public.keys("KeyCode");


--
-- TOC entry 3890 (class 2606 OID 16704)
-- Name: sources_servers sources_servers_format_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.sources_servers
    ADD CONSTRAINT sources_servers_format_fkey FOREIGN KEY (format) REFERENCES public.sources_formats(format);


--
-- TOC entry 3891 (class 2606 OID 16709)
-- Name: sources_stations sources_stations_NetworkCode_StationCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.sources_stations
    ADD CONSTRAINT "sources_stations_NetworkCode_StationCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES public.stations("NetworkCode", "StationCode");


--
-- TOC entry 3892 (class 2606 OID 16714)
-- Name: sources_stations sources_stations_format_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.sources_stations
    ADD CONSTRAINT sources_stations_format_fkey FOREIGN KEY (format) REFERENCES public.sources_formats(format);


--
-- TOC entry 3893 (class 2606 OID 16719)
-- Name: sources_stations sources_stations_server_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.sources_stations
    ADD CONSTRAINT sources_stations_server_id_fkey FOREIGN KEY (server_id) REFERENCES public.sources_servers(server_id);


--
-- TOC entry 3881 (class 2606 OID 16724)
-- Name: stacks stacks_NetworkCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stacks
    ADD CONSTRAINT "stacks_NetworkCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES public.stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 3882 (class 2606 OID 16729)
-- Name: stacks stacks_gamit_soln_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stacks
    ADD CONSTRAINT stacks_gamit_soln_fkey FOREIGN KEY ("Year", "DOY", "StationCode", "Project", "NetworkCode") REFERENCES public.gamit_soln("Year", "DOY", "StationCode", "Project", "NetworkCode") ON UPDATE CASCADE ON DELETE CASCADE;


--
-- TOC entry 3883 (class 2606 OID 16734)
-- Name: stationalias stationalias_fk; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stationalias
    ADD CONSTRAINT stationalias_fk FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES public.stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 3884 (class 2606 OID 16739)
-- Name: stationinfo stationinfo_AntennaCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stationinfo
    ADD CONSTRAINT "stationinfo_AntennaCode_fkey" FOREIGN KEY ("AntennaCode") REFERENCES public.antennas("AntennaCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 3885 (class 2606 OID 16744)
-- Name: stationinfo stationinfo_NetworkCode_StationCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stationinfo
    ADD CONSTRAINT "stationinfo_NetworkCode_StationCode_fkey" FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES public.stations("NetworkCode", "StationCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 3886 (class 2606 OID 16749)
-- Name: stationinfo stationinfo_ReceiverCode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.stationinfo
    ADD CONSTRAINT "stationinfo_ReceiverCode_fkey" FOREIGN KEY ("ReceiverCode") REFERENCES public.receivers("ReceiverCode") ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 3870 (class 2606 OID 16754)
-- Name: etm_params stations_fk; Type: FK CONSTRAINT; Schema: public; Owner: gnss_data_osu
--

ALTER TABLE ONLY public.etm_params
    ADD CONSTRAINT stations_fk FOREIGN KEY ("NetworkCode", "StationCode") REFERENCES public.stations("NetworkCode", "StationCode");


--
-- TOC entry 4085 (class 0 OID 0)
-- Dependencies: 5
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO PUBLIC;


-- Completed on 2024-12-06 13:37:02 EST

--
-- PostgreSQL database dump complete
--

