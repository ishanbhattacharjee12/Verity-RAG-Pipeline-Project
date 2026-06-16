"""POST /v1/ask — the full RAG question-answering pipeline."""

from fastapi import APIRouter

from models.documents import ErrorResponse
from models.query import AskRequest, AskResponse
from services.pipeline import answer_question

router = APIRouter(prefix="/v1", tags=["ask"])


@router.post(
    "/ask",
    response_model=AskResponse,
    responses={409: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def ask(request: AskRequest) -> AskResponse:
    """Retrieve (hybrid/dense/sparse) → rerank → generate → verify citations → score confidence."""
    return await answer_question(request)
