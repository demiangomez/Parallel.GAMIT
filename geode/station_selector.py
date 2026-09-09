"""
Improved station list processing with support for geographic filters and cleaner architecture.

Supports multiple filter types:
- Country codes: ARG, CHL
- Station types: ARG:CONTINUOUS, CHL:CAMPAIGN
- Geographic filters:
  - Bounding box: ARG:BBOX(-30,-40,-70,-60) or ARG:LAT(-30,-40):LON(-70,-60)
  - Radius: ARG:RADIUS(-35.5,-65.2,500) (lat, lon, radius_km)
  - Single coordinate ranges: ARG:LAT(-30,-40), ARG:LON(-70,-60)
  - Tectonic plate: ARG:PLATE(SA)
- Network.station notation with wildcards
- Station removals with - or * prefix
"""

import math
import re
from typing import List, Dict, Optional
import geopandas as gpd
from shapely.geometry import Point


def get_tectonic_plate(longitude, latitude):
    """
    Determine which tectonic plate a point is on.

    Parameters:
    -----------
    longitude : float
        Longitude in decimal degrees
    latitude : float
        Latitude in decimal degrees
    Returns:
    --------
    str or None : Name and code of the tectonic plate or None if not found
    """
    from importlib.resources import files
    data_path = files('geode.elasticity.data').joinpath('PB2002_plates.json')

    filename = str(data_path)

    plates = gpd.read_file(filename)

    point = Point(longitude, latitude)  # Note: Point takes (lon, lat)

    # Check which plate contains the point
    for idx, plate in plates.iterrows():
        if plate.geometry.contains(point):
            return plate['Code'], plate['PlateName']  # or use 'Code' for plate code

    return None, None


class StationFilter:
    """Represents a parsed station filter with all its components."""
    
    def __init__(self, filter_str: str):
        self.original = filter_str
        self.is_removal = filter_str.startswith(('-', '*'))
        self.parameters = []
        
        # Remove removal prefix if present
        filter_str = filter_str[1:] if self.is_removal else filter_str
        
        # Split off any additional parameters (space-separated)
        parts = filter_str.split()
        self.filter_str = parts[0]
        self.parameters = parts[1:] if len(parts) > 1 else []
        
        # Parse the main filter string
        self._parse_filter()
    
    def _parse_filter(self):
        """Parse the filter string into its components."""
        self.country_code = None
        self.network = None
        self.station = None
        self.station_type = None
        self.lat_range = None
        self.lon_range = None
        self.radius_filter = None
        self.tectonic_plate = None
        self.is_wildcard = False
        
        # Check for special keyword
        if self.filter_str == 'all':
            return
        
        # Parse components separated by colons
        components = self.filter_str.split(':')
        base = components[0]
        filters = components[1:] if len(components) > 1 else []
        
        # Determine if base is country code, network.station, or just station
        if '.' in base:
            # Network.station format
            self.network, self.station = base.split('.', 1)
        elif base.isupper():
            # Country code
            self.country_code = base
        else:
            # Just a station name
            self.station = base
        
        # Check for wildcards
        wildc = '[]%_|'
        if self.station and any(c in set(wildc) for c in self.station):
            self.is_wildcard = True
        
        # Parse additional filters
        for f in filters:
            self._parse_component_filter(f)
    
    def _parse_component_filter(self, filter_str: str):
        """Parse individual filter components like LAT(-30,-40) or CONTINUOUS."""
        # Try to match geographic filters
        lat_match = re.match(r'LAT\[([-\d.]+),([-\d.]+)]', filter_str)
        if lat_match:
            self.lat_range = (float(lat_match.group(1)), float(lat_match.group(2)))
            return
        
        lon_match = re.match(r'LON\[([-\d.]+),([-\d.]+)]', filter_str)
        if lon_match:
            self.lon_range = (float(lon_match.group(1)), float(lon_match.group(2)))
            return
        
        # BBOX is shorthand for LAT and LON
        bbox_match = re.match(r'BBOX\[([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)]', filter_str)
        if bbox_match:
            self.lat_range = (float(bbox_match.group(1)), float(bbox_match.group(2)))
            self.lon_range = (float(bbox_match.group(3)), float(bbox_match.group(4)))
            return
        
        # Radius filter: RADIUS(lat, lon, radius_km)
        radius_match = re.match(r'RADIUS\[([-\d.]+),([-\d.]+),([-\d.]+)]', filter_str)
        if radius_match:
            self.radius_filter = {
                'lat': float(radius_match.group(1)),
                'lon': float(radius_match.group(2)),
                'radius_km': float(radius_match.group(3))
            }
            return

        # PLATE filter allows to filter using tectonic plates
        plate_match = re.match(r'PLATE\[([-\w]+)]', filter_str)
        if plate_match:
            self.tectonic_plate = plate_match.group(1).upper()
            return

        # Otherwise assume it's a station type
        self.station_type = filter_str.upper()


class StationSelector:
    """Handles station selection queries from the database."""
    
    WILDCARD_CHARS = '[]%_|'
    
    def __init__(self, cnn):
        self.cnn = cnn
        self.has_studio_tables = self._check_studio_tables()
    
    def _check_studio_tables(self) -> bool:
        """Check if GeoDE Studio tables are available."""
        result = self.cnn.query_float("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name = 'api_stationtype'
            );
        """, as_dict=True)
        return result[0]['exists'] if result else False
    
    def select_stations(self, station_filter: StationFilter) -> List[Dict]:
        """Select stations based on the provided filter."""
        if station_filter.filter_str == 'all':
            # all:[filter] is a special case within _select_by_station
            return self._select_all_stations()
        
        if station_filter.country_code:
            return self._select_by_country(station_filter)
        
        if station_filter.network:
            return self._select_by_network(station_filter)
        
        if station_filter.station:
            return self._select_by_station(station_filter)
        
        return []
    
    def _select_all_stations(self) -> List[Dict]:
        """Select all stations."""
        query = '''SELECT * FROM stations 
                   WHERE "NetworkCode" NOT LIKE '?%%' 
                   ORDER BY "NetworkCode", "StationCode"'''
        rs = self.cnn.query(query)
        return rs.dictresult() if rs else []
    
    def _select_by_country(self, station_filter: StationFilter) -> List[Dict]:
        """Select stations by country code with optional filters."""
        base_query = '''SELECT stations.* FROM stations '''
        where_clauses = [
            '''"NetworkCode" NOT LIKE '?%%' ''',
            f'''country_code = '{station_filter.country_code}' '''
        ]
        
        # Add station type filter if present and tables exist
        if station_filter.station_type and self.has_studio_tables:
            st = self._get_station_type_id(station_filter.station_type)
            if st:
                base_query += '''LEFT JOIN api_stationmeta ON station_id = stations.api_id '''
                where_clauses.append(f'''station_type_id = {st} ''')
            else:
                print(f'Could not find station type filter {station_filter.station_type}. '
                      f'Available types: {self._get_available_station_types()}')
                return []
        elif station_filter.station_type and not self.has_studio_tables:
            print(f'Station type filter {station_filter.station_type} requested but '
                  f'GeoDE Studio tables are not present. Filter not applied.')
        
        # Add geographic filters
        geo_where = self._build_geographic_filter(station_filter)
        if geo_where:
            where_clauses.append(geo_where)
        
        query = base_query + ' WHERE ' + ' AND '.join(where_clauses)
        query += ''' ORDER BY "NetworkCode", "StationCode"'''
        
        rs = self.cnn.query(query)
        return rs.dictresult() if rs else []
    
    def _select_by_network(self, station_filter: StationFilter) -> List[Dict]:
        """Select stations by network and station code."""
        where_clauses = [
            f'''"NetworkCode" = '{station_filter.network}' ''',
            '''"NetworkCode" NOT LIKE '?%%' '''
        ]
        
        # Handle station selection
        if station_filter.station == 'all':
            # All stations from network
            pass
        elif station_filter.is_wildcard:
            where_clauses.append(f'''"StationCode" SIMILAR TO '{station_filter.station}' ''')
        else:
            where_clauses.append(f'''"StationCode" = '{station_filter.station}' ''')
        
        # Add geographic filters
        geo_where = self._build_geographic_filter(station_filter)
        if geo_where:
            where_clauses.append(geo_where)
        
        query = 'SELECT * FROM stations WHERE ' + ' AND '.join(where_clauses)
        query += ''' ORDER BY "NetworkCode", "StationCode"'''
        
        rs = self.cnn.query(query)
        return rs.dictresult() if rs else []
    
    def _select_by_station(self, station_filter: StationFilter) -> List[Dict]:
        """Select stations by station code only."""
        where_clauses = ['''"NetworkCode" NOT LIKE '?%%' ''']

        if station_filter.station == 'all':
            # this is an extreme case where the user did all:[filter] in which
            # case the StationFilter understood this is a station but in reality it is all stations
            pass
        elif station_filter.is_wildcard:
            where_clauses.append(f'''"StationCode" SIMILAR TO '{station_filter.station}' ''')
        else:
            where_clauses.append(f'''"StationCode" = '{station_filter.station}' ''')
        
        # Add geographic filters
        geo_where = self._build_geographic_filter(station_filter)
        if geo_where:
            where_clauses.append(geo_where)
        
        query = 'SELECT * FROM stations WHERE ' + ' AND '.join(where_clauses)
        query += ''' ORDER BY "NetworkCode", "StationCode"'''
        
        rs = self.cnn.query(query)
        return rs.dictresult() if rs else []

    @staticmethod
    def _build_geographic_filter(station_filter: StationFilter) -> Optional[str]:
        """Build SQL WHERE clause for geographic filters."""
        conditions = []
        
        if station_filter.lat_range:
            lat_min, lat_max = sorted(station_filter.lat_range)
            conditions.append(f'lat BETWEEN {lat_min} AND {lat_max}')
        
        if station_filter.lon_range:
            lon_min, lon_max = sorted(station_filter.lon_range)
            conditions.append(f'lon BETWEEN {lon_min} AND {lon_max}')
        
        if station_filter.radius_filter:
            # Using haversine distance formula in SQL
            # Note: This assumes you have lat/lon columns in decimal degrees
            rf = station_filter.radius_filter
            # Approximate degrees per km at this latitude. Longitude lines
            # converge toward the poles, so degrees-per-km scales with
            # 1/cos(lat) -- not linearly with |lat|. Near the poles
            # (cos(lat) ~ 0) any longitude is within a short distance of the
            # center, so no longitude bounding box is meaningful there.
            lat_deg_per_km = 1.0 / 111.0
            lat_delta = rf['radius_km'] * lat_deg_per_km

            bbox_conditions = [f"lat BETWEEN {rf['lat'] - lat_delta} AND {rf['lat'] + lat_delta}"]

            cos_lat = math.cos(math.radians(rf['lat']))
            if abs(cos_lat) > 1e-6:
                lon_deg_per_km = 1.0 / (111.0 * abs(cos_lat))
                lon_delta = rf['radius_km'] * lon_deg_per_km
                # if the radius already spans the full longitude range at
                # this latitude, a bounding box on lon restricts nothing
                if lon_delta < 180:
                    bbox_conditions.append(
                        f"lon BETWEEN {rf['lon'] - lon_delta} AND {rf['lon'] + lon_delta}")

            # Create a simple bounding box first for efficiency; the exact
            # great-circle distance check below is what actually determines
            # membership
            conditions.append('(' + ' AND '.join(bbox_conditions) + f'''
                AND (
                    6371 * acos(
                        cos(radians({rf['lat']})) * cos(radians(lat)) *
                        cos(radians(lon) - radians({rf['lon']})) +
                        sin(radians({rf['lat']})) * sin(radians(lat))
                    ) <= {rf['radius_km']}
                )
            )''')

        if station_filter.tectonic_plate:
            conditions.append(f'''plate = '{station_filter.tectonic_plate}' ''')
        
        return ' AND '.join(conditions) if conditions else None
    
    def _get_station_type_id(self, station_type: str) -> Optional[int]:
        """Get the ID for a station type."""
        rs = self.cnn.query_float(
            f"SELECT id FROM api_stationtype WHERE UPPER(name) = '{station_type}'",
            as_dict=True
        )
        return rs[0]['id'] if rs else None
    
    def _get_available_station_types(self) -> str:
        """Get a list of available station types."""
        rs = self.cnn.query_float('SELECT name FROM api_stationtype', as_dict=True)
        return ' '.join([t['name'].upper() for t in rs]) if rs else ''

