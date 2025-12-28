DROP TABLE IF EXISTS raw_station_data;

CREATE TABLE raw_station_data (
    timestamp TIMESTAMPTZ NOT NULL,
    rain DOUBLE PRECISION,
    wsmax DOUBLE PRECISION,
    wdmax DOUBLE PRECISION,
    ws DOUBLE PRECISION,
    wd DOUBLE PRECISION,
    stdwd DOUBLE PRECISION,
    td DOUBLE PRECISION,
    rh DOUBLE PRECISION,
    tdmax DOUBLE PRECISION,
    tdmin DOUBLE PRECISION,
    ws1mm DOUBLE PRECISION,
    ws10mm DOUBLE PRECISION,
    station_id INTEGER NOT NULL,
    latitude NUMERIC(7,4),
    longitude NUMERIC(7,4),

    -- Ensure never to get duplicate data for the same time
    CONSTRAINT unique_station_id_time UNIQUE (station_id, timestamp)
);