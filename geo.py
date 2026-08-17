import math
from datetime import datetime, time
from zoneinfo import ZoneInfo


INDIA_TZ = ZoneInfo("Asia/Kolkata")


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:

    earth_radius_km = 6371.0

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(dlon / 2) ** 2
    )

    return (
        earth_radius_km
        * 2
        * math.asin(math.sqrt(a))
    )


def get_local_now() -> datetime:
    return datetime.now(INDIA_TZ)


def is_within_shift(
    surveyor,
    current_time: datetime,
) -> bool:

    # Convert current time to India time
    current_time = current_time.astimezone(
        INDIA_TZ
    )

    start = time.fromisoformat(
        surveyor["shift_start"]
    )

    end = time.fromisoformat(
        surveyor["shift_end"]
    )

    current = current_time.time()

    if start <= end:
        return start <= current <= end

    # Overnight shift
    return (
        current >= start
        or current <= end
    )


def is_location_fresh(
    surveyor,
    current_time: datetime,
    max_age_seconds: int,
) -> bool:

    location_time = (
        surveyor["location_timestamp"]
    )

    # Make sure both are timezone-aware
    current_time = current_time.astimezone(
        location_time.tzinfo
    )

    age = (
        current_time - location_time
    ).total_seconds()

    return 0 <= age <= max_age_seconds