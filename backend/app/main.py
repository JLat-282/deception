from __future__ import annotations

from datetime import datetime
import re
import sqlite3
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import Settings
from .deception import DeceptionEngine
from .engine import TruthEngine, load_word_list
from .errors import DomainError
from .repository import Repository
from .schemas import (
    AttemptResponse,
    BootstrapResponse,
    ErrorBody,
    ErrorResponse,
    GuessRequest,
    HealthResponse,
    StartGameRequest,
    StartGameResponse,
    TimedOutResponse,
)
from .service import GameService, NowProvider, SeedProvider


DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,128}$")


def create_app(
    settings: Settings | None = None,
    now_provider: NowProvider | None = None,
    deception_engine: DeceptionEngine | None = None,
    session_seed_provider: SeedProvider | None = None,
) -> FastAPI:
    active_settings = settings or Settings.from_env()
    words = load_word_list(active_settings.data_dir / "words")
    answers = load_word_list(active_settings.data_dir / "answers")
    engine = TruthEngine(words, answers)
    active_deception_engine = deception_engine or DeceptionEngine(engine)
    repository = Repository(active_settings.db_path)
    resolved_now_provider = now_provider
    if resolved_now_provider is None and active_settings.fixed_now is not None:
        resolved_now_provider = lambda: active_settings.fixed_now
    service = GameService(
        active_settings,
        repository,
        engine,
        now_provider=resolved_now_provider,
        deception_engine=active_deception_engine,
        session_seed_provider=session_seed_provider,
    )

    app = FastAPI(
        title="Deception API",
        version="0.4.0",
    )
    app.state.service = service
    app.state.settings = active_settings

    @app.exception_handler(DomainError)
    async def domain_error_handler(
        _request: Request, error: DomainError
    ) -> JSONResponse:
        payload = ErrorResponse(
            error=ErrorBody(code=error.code, message=error.message)
        )
        return JSONResponse(
            status_code=error.status_code,
            content=payload.model_dump(by_alias=True),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, _error: RequestValidationError
    ) -> JSONResponse:
        payload = ErrorResponse(
            error=ErrorBody(
                code="INVALID_REQUEST",
                message="The request body is missing or invalid.",
            )
        )
        return JSONResponse(
            status_code=422,
            content=payload.model_dump(by_alias=True),
        )

    @app.exception_handler(sqlite3.Error)
    async def database_error_handler(
        _request: Request, _error: sqlite3.Error
    ) -> JSONResponse:
        payload = ErrorResponse(
            error=ErrorBody(
                code="SERVICE_UNAVAILABLE",
                message="Game storage is temporarily unavailable.",
            )
        )
        return JSONResponse(
            status_code=503,
            content=payload.model_dump(by_alias=True),
        )

    def device_id_for(request: Request, response: Response) -> str:
        cookie_name = active_settings.cookie_name
        existing = request.cookies.get(cookie_name)
        if existing and DEVICE_ID_PATTERN.fullmatch(existing):
            return existing

        device_id = service.new_device_id()
        response.set_cookie(
            key=cookie_name,
            value=device_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=active_settings.secure_cookie,
            samesite="lax",
            path="/",
        )
        return device_id

    @app.get(
        "/api/bootstrap",
        response_model=BootstrapResponse,
        response_model_by_alias=True,
    )
    def bootstrap(request: Request, response: Response) -> BootstrapResponse:
        return service.bootstrap(device_id_for(request, response))

    @app.post(
        "/api/games",
        response_model=StartGameResponse,
        response_model_by_alias=True,
        response_model_exclude_none=True,
    )
    def start_game(
        payload: StartGameRequest,
        request: Request,
        response: Response,
    ) -> StartGameResponse:
        return service.start_game(
            device_id_for(request, response), payload.mode
        )

    @app.post(
        "/api/games/{game_id}/guesses",
        response_model=AttemptResponse,
        response_model_by_alias=True,
        response_model_exclude_none=True,
    )
    def submit_guess(
        game_id: str,
        payload: GuessRequest,
        request: Request,
        response: Response,
    ) -> AttemptResponse:
        return service.submit_guess(
            device_id_for(request, response), game_id, payload.guess
        )

    @app.post(
        "/api/games/{game_id}/timer/expire",
        response_model=TimedOutResponse,
        response_model_by_alias=True,
        response_model_exclude_none=True,
    )
    def expire_timer(
        game_id: str,
        request: Request,
        response: Response,
    ) -> TimedOutResponse:
        return service.expire_timer(
            device_id_for(request, response), game_id
        )

    @app.get(
        "/api/health",
        response_model=HealthResponse,
        response_model_by_alias=True,
    )
    def health() -> HealthResponse:
        repository.health()
        return HealthResponse(status="ok", database="ok")

    return app


app = create_app()
