import asyncio


async def send_notification(
    claim_id: str,
    tier: int,
    surveyor: dict,
):

    print(
        f"[NOTIFICATION] "
        f"claim={claim_id} "
        f"tier={tier} "
        f"surveyor="
        f"{surveyor['surveyor_id']} "
        f"type={surveyor['type']} "
        f"distance="
        f"{surveyor['distance_km']}km"
    )

    # Simulate async notification
    await asyncio.sleep(0)