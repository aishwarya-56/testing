import asyncio


dispatch_states = {}

dispatch_locks = {}

dispatch_tasks = {}


def get_claim_lock(
    claim_id: str,
) -> asyncio.Lock:

    if claim_id not in dispatch_locks:

        dispatch_locks[
            claim_id
        ] = asyncio.Lock()

    return dispatch_locks[
        claim_id
    ]