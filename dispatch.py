import asyncio
from typing import Optional

from config import (
    TIER_CONFIG,
    MAX_LOCATION_AGE_SECONDS,
)

from geo import (
    get_local_now,
    haversine_km,
    is_location_fresh,
    is_within_shift,
)

from notification import send_notification
from state import dispatch_states, get_claim_lock
from surveyor_service import get_surveyors


# ============================================================
# Utility: convert surveyor to API response format
# ============================================================

def format_surveyor(surveyor: dict) -> dict:
    return {
        "surveyor_id": surveyor["surveyor_id"],
        "type": surveyor["type"],
        "distance_km": surveyor["distance_km"],
    }


# ============================================================
# Find eligible surveyors for a tier
# ============================================================

def get_tier_candidates(
    accident,
    surveyors,
    tier: int,
) -> list[dict]:

    config = TIER_CONFIG[tier]

    now = get_local_now()

    candidates = []

    for surveyor in surveyors:

        # ----------------------------------------------------
        # Surveyor type
        # ----------------------------------------------------

        if surveyor["type"] not in config["surveyor_types"]:
            continue

        # ----------------------------------------------------
        # Availability
        # ----------------------------------------------------

        if surveyor["availability"] != "AVAILABLE":
            continue

        # ----------------------------------------------------
        # Location freshness
        # ----------------------------------------------------

        if not is_location_fresh(
            surveyor,
            now,
            MAX_LOCATION_AGE_SECONDS,
        ):
            continue

        # ----------------------------------------------------
        # Shift
        # ----------------------------------------------------

        if not is_within_shift(
            surveyor,
            now,
        ):
            continue

        # ----------------------------------------------------
        # Haversine distance
        # ----------------------------------------------------

        distance = haversine_km(
            accident.latitude,
            accident.longitude,
            surveyor["latitude"],
            surveyor["longitude"],
        )

        # ----------------------------------------------------
        # Radius
        # ----------------------------------------------------

        if distance > config["radius_km"]:
            continue

        candidate = dict(surveyor)

        candidate["distance_km"] = round(
            distance,
            2,
        )

        candidates.append(candidate)

    # Closest first
    candidates.sort(
        key=lambda x: x["distance_km"]
    )

    # Only notify the configured number
    return candidates[
        :config["notify_count"]
    ]


# ============================================================
# Send notifications
# ============================================================

async def notify_candidates(
    claim_id: str,
    tier: int,
    candidates: list[dict],
):
    """
    Send notifications concurrently.

    In production this will eventually publish
    notification events to Kafka.
    """

    if not candidates:
        return

    await asyncio.gather(
        *[
            send_notification(
                claim_id,
                tier,
                surveyor,
            )
            for surveyor in candidates
        ]
    )


# ============================================================
# Update state after candidates are found
# ============================================================

def update_state_for_candidates(
    claim_id: str,
    tier: int,
    candidates: list[dict],
):
    state = dispatch_states[claim_id]

    state["current_tier"] = tier

    state["status"] = (
        "WAITING_FOR_ACCEPTANCE"
    )

    state["notified_surveyors"] = [
        s["surveyor_id"]
        for s in candidates
    ]

    state["tier_history"].append({
        "tier": tier,
        "status": "NOTIFICATION_SENT",
        "surveyors": [
            format_surveyor(s)
            for s in candidates
        ],
    })


# ============================================================
# Record that a tier had no candidates
# ============================================================

def record_no_candidates(
    claim_id: str,
    tier: int,
):
    dispatch_states[
        claim_id
    ]["tier_history"].append({
        "tier": tier,
        "status": "NO_SURVEYOR_FOUND",
    })


# ============================================================
# Find candidates for a tier
# ============================================================

def find_candidates(
    accident,
    tier: int,
):
    surveyors = get_surveyors()

    return get_tier_candidates(
        accident,
        surveyors,
        tier,
    )


# ============================================================
# Start waiting timer
# ============================================================

async def wait_for_tier_timeout(
    claim_id: str,
    tier: int,
):
    """
    Wait for the tier's acceptance timeout.

    IMPORTANT:
    This function does NOT hold the claim lock while sleeping.
    """

    wait_seconds = TIER_CONFIG[tier][
        "wait_seconds"
    ]

    await asyncio.sleep(
        wait_seconds
    )

    # --------------------------------------------------------
    # Check state after timeout
    # --------------------------------------------------------

    async with get_claim_lock(claim_id):

        state = dispatch_states.get(
            claim_id
        )

        if not state:
            return

        # Someone accepted
        if state["status"] == "ACCEPTED":
            return

        # Already finished
        if state["status"] == "NO_SURVEYOR_ACCEPTED":
            return

    # --------------------------------------------------------
    # Move to next tier OUTSIDE the lock
    #
    # This avoids re-entrant asyncio.Lock problems.
    # --------------------------------------------------------

    next_tier = tier + 1

    if next_tier > 3:

        async with get_claim_lock(
            claim_id
        ):

            state = dispatch_states.get(
                claim_id
            )

            if not state:
                return

            if state["status"] != "ACCEPTED":

                state["status"] = (
                    "NO_SURVEYOR_ACCEPTED"
                )

        return

    await execute_tier(
        claim_id,
        next_tier,
    )


# ============================================================
# Execute a tier
# ============================================================

async def execute_tier(
    claim_id: str,
    tier: int,
):
    """
    Execute a tier.

    If candidates are found:
        notify them
        start timeout

    If candidates are NOT found:
        immediately move to next tier.
    """

    state = dispatch_states.get(
        claim_id
    )

    if not state:
        return

    if state["status"] == "ACCEPTED":
        return

    accident = state["accident"]

    # --------------------------------------------------------
    # Find candidates
    # --------------------------------------------------------

    candidates = find_candidates(
        accident,
        tier,
    )

    # --------------------------------------------------------
    # No candidates
    # --------------------------------------------------------

    if not candidates:

        async with get_claim_lock(
            claim_id
        ):

            state = dispatch_states.get(
                claim_id
            )

            if not state:
                return

            if state["status"] == "ACCEPTED":
                return

            record_no_candidates(
                claim_id,
                tier,
            )

        # Move immediately to next tier
        if tier < 3:

            await execute_tier(
                claim_id,
                tier + 1,
            )

        else:

            async with get_claim_lock(
                claim_id
            ):

                state = dispatch_states.get(
                    claim_id
                )

                if state:
                    state["status"] = (
                        "NO_SURVEYOR_ACCEPTED"
                    )

        return

    # --------------------------------------------------------
    # Candidates found
    # --------------------------------------------------------

    async with get_claim_lock(
        claim_id
    ):

        state = dispatch_states.get(
            claim_id
        )

        if not state:
            return

        if state["status"] == "ACCEPTED":
            return

        update_state_for_candidates(
            claim_id,
            tier,
            candidates,
        )

    # --------------------------------------------------------
    # Send notifications
    # --------------------------------------------------------

    await notify_candidates(
        claim_id,
        tier,
        candidates,
    )

    # --------------------------------------------------------
    # Start timeout task
    #
    # DO NOT await it.
    # --------------------------------------------------------

    task = asyncio.create_task(
        wait_for_tier_timeout(
            claim_id,
            tier,
        )
    )

    # Keep reference to background task
    state = dispatch_states.get(
        claim_id
    )

    if state is not None:

        state.setdefault(
            "background_tasks",
            [],
        ).append(task)


# ============================================================
# Start dispatch
# ============================================================

async def start_dispatch(
    accident,
):
    """
    Entry point for a new claim.

    Tier 1 is evaluated immediately so that the API
    can return the closest surveyor in its response.

    If Tier 1 has no candidates, Tier 2 is evaluated
    immediately, and similarly Tier 3.
    """

    claim_id = accident.claim_id

    # --------------------------------------------------------
    # Create claim state
    # --------------------------------------------------------

    async with get_claim_lock(
        claim_id
    ):

        if claim_id in dispatch_states:

            raise ValueError(
                "Dispatch already exists"
            )

        dispatch_states[
            claim_id
        ] = {
            "claim_id":
                claim_id,

            "accident":
                accident,

            "current_tier":
                None,

            "status":
                "STARTING",

            "notified_surveyors":
                [],

            "accepted_surveyor":
                None,

            "accepted_tier":
                None,

            "tier_history":
                [],

            "background_tasks":
                [],
        }

    # --------------------------------------------------------
    # Execute Tier 1
    # --------------------------------------------------------

    await execute_tier(
        claim_id,
        1,
    )

    # --------------------------------------------------------
    # Build immediate response
    # --------------------------------------------------------

    async with get_claim_lock(
        claim_id
    ):

        state = dispatch_states.get(
            claim_id
        )

        if not state:
            raise ValueError(
                "Dispatch state disappeared"
            )

        response = {
            "claim_id":
                claim_id,

            "status":
                state["status"],

            "current_tier":
                state["current_tier"],

            "notified_surveyors": [],
        }

        # Find latest tier history entry
        if state["tier_history"]:

            latest = state[
                "tier_history"
            ][-1]

            if (
                latest["status"]
                == "NOTIFICATION_SENT"
            ):

                response[
                    "notified_surveyors"
                ] = latest["surveyors"]

                response[
                    "acceptance_timeout_seconds"
                ] = TIER_CONFIG[
                    latest["tier"]
                ]["wait_seconds"]

        return response


# ============================================================
# Accept claim
# ============================================================

async def accept_claim(
    claim_id: str,
    surveyor_id: str,
):
    """
    Accept a claim on behalf of a surveyor.

    The surveyor must have been notified for the
    currently active tier.
    """

    async with get_claim_lock(
        claim_id
    ):

        state = dispatch_states.get(
            claim_id
        )

        if not state:
            return None

        # ----------------------------------------------------
        # Already accepted
        # ----------------------------------------------------

        if state["status"] == "ACCEPTED":

            raise ValueError(
                "Claim has already been accepted"
            )

        # ----------------------------------------------------
        # Dispatch ended
        # ----------------------------------------------------

        if (
            state["status"]
            == "NO_SURVEYOR_ACCEPTED"
        ):

            raise ValueError(
                "Claim dispatch has already ended"
            )

        # ----------------------------------------------------
        # Check surveyor notification
        # ----------------------------------------------------

        if (
            surveyor_id
            not in state["notified_surveyors"]
        ):

            raise ValueError(
                "Surveyor was not notified for "
                "this claim"
            )

        # ----------------------------------------------------
        # Accept
        # ----------------------------------------------------

        state["status"] = "ACCEPTED"

        state[
            "accepted_surveyor"
        ] = surveyor_id

        state[
            "accepted_tier"
        ] = state["current_tier"]

        return {
            "claim_id":
                claim_id,

            "status":
                "ACCEPTED",

            "tier":
                state["current_tier"],

            "surveyor_id":
                surveyor_id,
        }


# ============================================================
# Get claim status
# ============================================================

async def get_claim_status(
    claim_id: str,
) -> Optional[dict]:

    async with get_claim_lock(
        claim_id
    ):

        state = dispatch_states.get(
            claim_id
        )

        if not state:
            return None

        return {
            "claim_id":
                state["claim_id"],

            "status":
                state["status"],

            "current_tier":
                state["current_tier"],

            "notified_surveyors":
                state[
                    "notified_surveyors"
                ],

            "accepted_surveyor":
                state[
                    "accepted_surveyor"
                ],

            "accepted_tier":
                state[
                    "accepted_tier"
                ],

            "tier_history":
                state[
                    "tier_history"
                ],
        }