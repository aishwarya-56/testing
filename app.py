from fastapi import (
    FastAPI,
    HTTPException,
)

from models import (
    AccidentRequest,
    SurveyorAcceptance,
)

from dispatch import (
    start_dispatch,
    accept_claim,
    get_claim_status,
)

from state import (
    dispatch_states,
)


app = FastAPI(
    title="Motor Surveyor Dispatch API",
    version="0.1.0",
)


@app.get("/health")
async def health():

    return {
        "status": "UP"
    }


@app.post(
    "/api/v1/claims/dispatch"
)
async def dispatch(
    accident: AccidentRequest,
):

    try:

        return await start_dispatch(
            accident
        )

    except ValueError as e:

        raise HTTPException(
            status_code=409,
            detail=str(e),
        )


@app.post(
    "/api/v1/claims/{claim_id}/accept"
)
async def accept(
    claim_id: str,
    request: SurveyorAcceptance,
):

    try:

        result = await accept_claim(
            claim_id,
            request.surveyor_id,
        )

        if result is None:

            raise HTTPException(
                status_code=404,
                detail="Claim not found",
            )

        return result

    except ValueError as e:

        raise HTTPException(
            status_code=409,
            detail=str(e),
        )

@app.get(
    "/api/v1/claims/{claim_id}/status"
)
async def status(
    claim_id: str,
):

    state = await get_claim_status(
        claim_id
    )

    if not state:

        raise HTTPException(
            status_code=404,
            detail="Claim not found",
        )

    return state