from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentSession, get_llm_service
from app.core.exceptions import LLMError
from app.db.models.session import Session
from app.schemas.llm import ParsePromptRequest, ParsePromptResponse
from app.services.llm_service import LLMService

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/parse", response_model=ParsePromptResponse)
async def parse_prompt(
    body: ParsePromptRequest,
    _session: Session = CurrentSession,
    llm: LLMService = Depends(get_llm_service),
) -> ParsePromptResponse:
    try:
        profile = await llm.parse_prompt(
            body.prompt,
            track_count=body.track_count,
            instrumental_only=body.instrumental_only,
        )
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return ParsePromptResponse(profile=profile)
