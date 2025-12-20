import pytest
import pandas as pd
import numpy as np
import os
from sqlalchemy import create_engine, inspect, types
from dotenv import load_dotenv

@pytest.fixture
def sample_bronze_data():
    """
    Returns all bronze layer data in a pandas dataframe
    """
    load_dotenv()

    db_user = os.getenv("POSTGRES_USER")
    db_pass = os.getenv("POSTGRES_PASSWORD")
    db_host = os.getenv("POSTGRES_HOST")
    db_name = os.getenv("POSTGRES_DB")

    if not db_host:
        pytest.fail("Environment variables failed to load! Check your .env file.")

    DB_CONN_STR = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:5432/{db_name}"

    try:
        engine = create_engine(DB_CONN_STR)
        df = pd.read_sql("raw_station_data", engine)
        return df
    except Exception as e:
        pytest.fail(f"Database connection failed. Ensure Docker is running.\nError: {e}")

def test_no_negative_rain(sample_bronze_data):
    """
    Integrity Check: Rain cannot be negative.
    """
    valid_rain = sample_bronze_data["rain"].dropna()

    if valid_rain.empty:
        pytest.skip("Skipping: No valid rain data found.")
    
    bad_rows = valid_rain[valid_rain < 0]
    assert bad_rows.empty, f"Found {len(bad_rows)} negative rain values! Examples: \n{bad_rows.head()}"

def test_temperature_absolute_bounds(sample_bronze_data):
    """
    Integrity Check: Temperature must be realistic
    """
    MIN_REALISTIC_TEMP = -10.0
    MAX_REALISTIC_TEMP = 50.0
    cols_to_check = ['td', 'tdmax', 'tdmin']

    for col in cols_to_check:
        # Get only existing numbers
        valid_temps = sample_bronze_data[col].dropna()
        
        if valid_temps.empty:
            continue

        # Check Lower Bound
        too_cold = valid_temps[valid_temps < MIN_REALISTIC_TEMP]
        assert too_cold.empty, \
            f"Found impossibly low temps in {col}. Examples: \n{too_cold.head()}"
        
        # Check Upper Bound
        too_hot = valid_temps[valid_temps > MAX_REALISTIC_TEMP]
        assert too_hot.empty, \
            f"Found impossibly high temps in {col}. Examples: \n{too_hot.head()}"

def test_temp_consistency_logic(sample_bronze_data):
    """
    Logic Check: T_max >= T_current >= T_min
    It is physically impossible for the current temp to be higher than the daily max
    or lower than the daily min.
    """
    max_violation = sample_bronze_data[sample_bronze_data['td'] > sample_bronze_data['tdmax']]
    assert max_violation.empty, \
        f"Logic Error: Found {len(max_violation)} rows where T_current > T_max.\n{max_violation}"

    min_violation = sample_bronze_data[sample_bronze_data['td'] < sample_bronze_data['tdmin']]
    assert min_violation.empty, \
        f"Logic Error: Found {len(min_violation)} rows where T_current < T_min.\n{min_violation}"
    
    inverted_range = sample_bronze_data[sample_bronze_data['tdmax'] < sample_bronze_data['tdmin']]
    assert inverted_range.empty, \
        f"Logic Error: Found {len(inverted_range)} rows where T_max < T_min (Inverted range)."