DROP TABLE IF EXISTS raw_station_data;

CREATE TABLE raw_station_data (
    -- SQLite stores datetimes as ISO8601 strings (TEXT) or Real numbers.
    -- We use TEXT to keep it human-readable and compatible with Pandas.
    timestamp TEXT NOT NULL, 
    
    -- DOUBLE PRECISION maps to REAL in SQLite
    rain REAL,
    wsmax REAL,
    wdmax REAL,
    ws REAL,
    wd REAL,
    stdwd REAL,
    td REAL,
    rh REAL,
    tdmax REAL,
    tdmin REAL,
    ws1mm REAL,
    ws10mm REAL,
    
    station_id INTEGER NOT NULL,
    
    -- SQLite ignores precision (7,4), but keeps NUMERIC affinity
    latitude NUMERIC,
    longitude NUMERIC,

    -- Constraint syntax is identical
    CONSTRAINT unique_station_id_time UNIQUE (station_id, timestamp)
);