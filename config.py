# config.py

from pathlib import Path

import yaml


# ============================================================
# Load YAML
# ============================================================

CONFIG_FILE = (
    Path(__file__).parent
    / "config.yml"
)


with open(
    CONFIG_FILE,
    "r",
    encoding="utf-8",
) as f:

    CONFIG = yaml.safe_load(f)


# ============================================================
# Dispatch configuration
# ============================================================

DISPATCH_CONFIG = CONFIG[
    "dispatch"
]


# ============================================================
# Location configuration
# ============================================================

MAX_LOCATION_AGE_SECONDS = (
    DISPATCH_CONFIG[
        "max_location_age_seconds"
    ]
)


# ============================================================
# Tier configuration
# ============================================================

TIER_CONFIG = {}

for tier, tier_config in (
    DISPATCH_CONFIG["tiers"].items()
):

    TIER_CONFIG[int(tier)] = {
        "radius_km":
            tier_config["radius_km"],

        "notify_count":
            tier_config["notify_count"],

        "wait_seconds":
            tier_config["wait_seconds"],

        "surveyor_types":
            tier_config["surveyor_types"],
    }