import pytest
import pandas as pd
import numpy as np
from weather_engine.database import engine

def get_wind_components(ws, wd):
    wd_rad = np.deg2rad(wd)
    u = -ws * np.sin(wd_rad)
    v = -ws * np.cos(wd_rad)
    return u, v

@pytest.fixture(scope="session")
def sample_bronze_data():
    """
    Returns all bronze layer data in a pandas dataframe
    """
    query = """
    WITH RankedData AS (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY station_id 
                   ORDER BY timestamp DESC
               ) as rank
        FROM raw_station_data
    )
    SELECT * FROM RankedData 
    WHERE rank <= 2000;
    """

    try:
        return pd.read_sql(query, engine) 
    except Exception as e:
        pytest.fail(f"Database connection failed. Ensure Docker is running.\nError: {e}")

# @pytest.fixture(scope="session")
# def sample_silver_data():
#     """
#     Returns all silver layer data in a pandas dataframe
#     """
#     try:
#         return pd.read_sql("clean_station_data", engine)
#     except Exception as e:
#         pytest.fail(f"Database connection failed. Ensure Docker is running.\nError: {e}")

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

def test_wind_vector_aggregation_logic():
    """
    Verifies that aggregating wind vectors handles the 'North Problem' (350 vs 10 degrees)
    correctly, unlike simple scalar averaging.
    """
    data = {
        "timestamp": pd.date_range(start="2025-01-01 10:00", periods=6, freq="10min"),
        "ws": [10, 10, 10, 10, 10, 10],  # Constant strong wind
        "wd": [350, 10, 350, 10, 350, 10] # Swinging across North
    }
    df = pd.DataFrame(data)

    df['u'], df['v'] = get_wind_components(df['ws'], df['wd'])
    
    hourly_agg = df.set_index('timestamp').resample('1h').agg({
        'u': 'mean',
        'v': 'mean'
    }).reset_index()

    result_u = hourly_agg['u'].iloc[0]
    result_v = hourly_agg['v'].iloc[0]

    # CHECK U (East-West): 
    # sin(350) is ~ -0.17, sin(10) is ~ +0.17. They should almost cancel out to 0.
    assert np.isclose(result_u, 0, atol=0.1), \
        f"Expected U component to cancel out near 0, got {result_u}"

    # CHECK V (North-South):
    # Both 350 and 10 degrees are from North, so V should be strongly negative (blowing South).
    # -10 * cos(10) is roughly -9.8.
    assert result_v < -9.0, \
        f"Expected V component to be strongly negative (North Wind), got {result_v}"
        
    print(f"\nSUCCESS: Aggregated Vector is U={result_u:.2f}, V={result_v:.2f}")
    print("Logic confirms: Wind is blowing FROM North (approx 0 degrees) despite crossing the 360/0 boundary.")

def test_wind_cancellation_logic():
    """
    Verifies that opposing winds cancel each other out (Simulating a calm average).
    """
    # 30 mins of North Wind (0 deg), 30 mins of South Wind (180 deg) at same speed
    data = {
        "ws": [10, 10, 10, 10, 10, 10], 
        "wd": [0, 0, 0, 180, 180, 180] 
    }
    df = pd.DataFrame(data)
    
    df['u'], df['v'] = get_wind_components(df['ws'], df['wd'])
    
    # Manually mean them (simulating the aggregation)
    avg_u = df['u'].mean()
    avg_v = df['v'].mean()

    # U should be 0 (North/South have no East/West component)
    assert np.isclose(avg_u, 0, atol=0.01)
    
    # V should be 0 (10m/s North cancels 10m/s South)
    assert np.isclose(avg_v, 0, atol=0.01), f"Expected V to cancel to 0, got {avg_v}"