import random
from datetime import datetime, timezone


def get_surveyors():

    random.seed()

    surveyors = []

    base_lat = 12.9716
    base_lon = 77.5946

    for i in range(100):

        if i < 20:

            lat = base_lat + random.uniform(
                -0.03,
                0.03,
            )

            lon = base_lon + random.uniform(
                -0.03,
                0.03,
            )

        else:

            lat = base_lat + random.uniform(
                -0.15,
                0.15,
            )

            lon = base_lon + random.uniform(
                -0.15,
                0.15,
            )

        surveyor_type = (
            "INTERNAL"
            if i < 70
            else "OUTSOURCE"
        )

        surveyors.append(
            {
                "surveyor_id":
                    f"S{i + 1:03d}",

                "latitude":lat,

                "longitude":lon,

                "type":
                    surveyor_type,

                "availability":
                    random.choice(
                        [
                            "AVAILABLE",
                            "AVAILABLE",
                            "BUSY",
                        ]
                    ),

                "shift_start": "11:00",

                "shift_end": "00:00",

                "location_timestamp":
                    datetime.now(
                        timezone.utc
                    ),
            }
        )

    return surveyors