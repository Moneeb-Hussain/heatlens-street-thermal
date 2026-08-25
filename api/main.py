from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.deps import get_settings
from api.routes import router
from api.schemas import ErrorBody, error_status
from heatlens.errors import HeatLensError


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="HeatLens API",
        version="0.1.0",
        description="Street-level thermal anomaly serving layer.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
    application.include_router(router)

    @application.exception_handler(HeatLensError)
    async def heatlens_error(_, exc: HeatLensError):
        body = ErrorBody(code=exc.code, message=str(exc))
        return JSONResponse(status_code=error_status(exc), content=body.model_dump())

    return application


app = create_app()
