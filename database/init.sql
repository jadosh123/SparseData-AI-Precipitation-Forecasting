DROP TABLE IF EXISTS cell_forecasts;
DROP TABLE IF EXISTS cell_interpolated;
-- DROP TABLE IF EXISTS cell_neighbors;
-- DROP TABLE IF EXISTS station_neighbors;
-- DROP TABLE IF EXISTS clean_station_data;
-- DROP TABLE IF EXISTS raw_station_data;
-- DROP TABLE IF EXISTS station_metadata;

CREATE TABLE IF NOT EXISTS station_metadata (
    station_id INTEGER PRIMARY KEY,
    latitude REAL,
    longitude REAL,
    elevation REAL,
    tpi_local REAL,
    tpi_regional REAL,
    roughness_local REAL,
    roughness_regional REAL,
    dist_to_coast REAL
);

CREATE TABLE IF NOT EXISTS clean_station_data (
    station_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    rain REAL,
    ws REAL,
    td REAL,
    rh REAL,
    tdmax REAL,
    tdmin REAL,
    u_vec REAL,
    v_vec REAL,
    CONSTRAINT unique_clean_station_id_time UNIQUE (station_id, timestamp)
);

CREATE TABLE IF NOT EXISTS cell_neighbors (
    cell_id INTEGER PRIMARY KEY AUTOINCREMENT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    is_boundary INTEGER NOT NULL,
    neighbor_1_id INTEGER NOT NULL,
    neighbor_1_distance REAL NOT NULL,
    neighbor_2_id INTEGER NOT NULL,
    neighbor_2_distance REAL NOT NULL,
    neighbor_3_id INTEGER NOT NULL,
    neighbor_3_distance REAL NOT NULL,
    elevation REAL,
    dist_to_coast REAL,
    tpi_local REAL,
    tpi_regional REAL,
    roughness_local REAL,
    roughness_regional REAL,
    CONSTRAINT unique_cell_lat_lon UNIQUE (lat, lon)
);

CREATE TABLE IF NOT EXISTS cell_interpolated (
    cell_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    rain REAL,
    ws REAL,
    td REAL,
    rh REAL,
    tdmax REAL,
    tdmin REAL,
    u_vec REAL,
    v_vec REAL,
    CONSTRAINT unique_cell_interpolated UNIQUE (cell_id, timestamp),
    FOREIGN KEY (cell_id) REFERENCES cell_neighbors (cell_id)
);

CREATE TABLE IF NOT EXISTS cell_forecasts (
    cell_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    precipitation_t1 REAL,
    precipitation_t3 REAL,
    precipitation_t6 REAL,
    precipitation_t12 REAL,
    CONSTRAINT unique_cell_forecast UNIQUE (cell_id, timestamp),
    FOREIGN KEY (cell_id) REFERENCES cell_neighbors (cell_id)
);

CREATE TABLE IF NOT EXISTS raw_station_data (
    timestamp TEXT NOT NULL, 
    rain REAL,
    ws REAL,
    wd REAL,
    stdwd REAL,
    td REAL,
    rh REAL,
    tdmax REAL,
    tdmin REAL,
    station_id INTEGER NOT NULL,
    CONSTRAINT unique_station_id_time UNIQUE (station_id, timestamp)
);