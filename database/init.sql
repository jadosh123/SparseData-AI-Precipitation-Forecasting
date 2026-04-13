DROP TABLE IF EXISTS station_neighbors;
DROP TABLE IF EXISTS clean_station_data;
DROP TABLE IF EXISTS raw_station_data;
DROP TABLE IF EXISTS station_metadata;

CREATE TABLE station_metadata (
    station_id INTEGER PRIMARY KEY,
    latitude NUMERIC,
    longitude NUMERIC,
    elevation NUMERIC
);

CREATE TABLE clean_station_data (
    timestamp TEXT NOT NULL,
    rain REAL,
    ws REAL,
    stdwd REAL,
    td REAL,
    rh REAL,
    tdmax REAL,
    tdmin REAL,
    u_vec REAL,
    v_vec REAL,
    station_id INTEGER NOT NULL,
    CONSTRAINT unique_clean_station_id_time UNIQUE (station_id, timestamp)
);

CREATE TABLE station_neighbors (
    station_id INTEGER PRIMARY KEY,
    is_boundary INTEGER NOT NULL,
    triangle_area REAL,
    neighbor_1_id INTEGER NOT NULL,
    neighbor_1_distance REAL NOT NULL,
    neighbor_2_id INTEGER NOT NULL,
    neighbor_2_distance REAL NOT NULL,
    neighbor_3_id INTEGER NOT NULL,
    neighbor_3_distance REAL NOT NULL
);

CREATE TABLE raw_station_data (
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