import secrets
import asyncio
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from .config import Config
from .inference import Ollama, ServiceError
from .schemas import TranslateRequest, AnalysisRequest, VocabularyRequest, EncounterRequest
from .study import JapaneseStudy
from .vocabulary import VocabularyStore
from .anki import Anki


def create_app(config=None, inference=None):
    config = config or Config.from_env()
    inference = inference or Ollama(config)
    study = JapaneseStudy(config.data_dir.resolve())
    vocabulary = VocabularyStore(config.data_dir)
    anki = Anki(config)
    anki_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app):
        yield
        await inference.client.aclose()

    async def authenticate(request: Request):
        supplied = request.headers.get("authorization", "")
        if not secrets.compare_digest(supplied.encode(), ("Bearer " + config.token).encode()):
            raise ServiceError("unauthorized", "Pair the Deck using the Workbench access token.", 401)

    app = FastAPI(title="dross-translation-server", version="0.1.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None, dependencies=[Depends(authenticate)])
    app.state.config, app.state.inference = config, inference

    @app.middleware("http")
    async def limit_body(request: Request, call_next):
        # Never log request bodies, source text, tokens or images.
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 4_000_000:
            return JSONResponse({"error": "request_too_large", "message": "Request exceeds 4 MB."}, status_code=413)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4_000_000:
                return JSONResponse({"error": "request_too_large", "message": "Request exceeds 4 MB."}, status_code=413)
        # Starlette's cached request replays this bounded body to downstream routes.
        request._body = bytes(body)
        return await call_next(request)

    @app.exception_handler(ServiceError)
    async def service_error(request, exc):
        return JSONResponse({"error": exc.code, "message": exc.message}, status_code=exc.status)

    @app.get("/health")
    async def health():
        try:
            models = await inference.models()
            translation = config.translation_model in models
            analysis = config.analysis_model in models
            identity = await inference.identity(config.translation_model) if translation else None
            return {"status": "ok" if translation else "degraded", "version": "0.1.0",
                    "translation_model": config.translation_model, "analysis_model": config.analysis_model,
                    "translation_available": translation, "analysis_available": analysis,
                    "model_identity": identity, "local_only": True,
                    "context_supported": not config.translation_model.startswith("translategemma"),
                    "screenshots_allowed": config.allow_images}
        except ServiceError as e:
            return JSONResponse({"status": "degraded", "translation_available": False,
                                 "error": e.code, "message": e.message}, status_code=503)

    @app.post("/v1/translate")
    async def translate(body: TranslateRequest):
        return await inference.translate(body)

    @app.post('/v1/analyze')
    async def analyze(body: AnalysisRequest):
        result = await asyncio.to_thread(study.analyze, body.text)
        result['translation'] = body.translation
        if body.explain:
            result['grammar'] = await study.explain(body, inference)
        return result

    @app.post('/v1/vocabulary')
    async def save_vocabulary(body: VocabularyRequest):
        if body.screenshot_base64 and not config.allow_images:
            raise ServiceError('screenshots_disabled', 'Enable optional screenshots on both Workbench and the Deck first.', 403)
        item = await asyncio.to_thread(vocabulary.save, body)
        if body.sync_anki:
            async with anki_lock:
                full = next(x for x in await asyncio.to_thread(vocabulary.list, body.game_id) if x['id'] == item['id'])
                try:
                    item['anki_id'] = await anki.sync(full, body.game_subdeck)
                    await asyncio.to_thread(vocabulary.set_anki_id, item['id'], item['anki_id'])
                except ServiceError as e:
                    item['anki_error'] = e.message  # Local save still succeeds.
        return item

    @app.post('/v1/vocabulary/encounters')
    async def record_encounters(body: EncounterRequest):
        return {'recorded': await asyncio.to_thread(vocabulary.record_encounters, body, study)}

    @app.get('/v1/vocabulary')
    async def list_vocabulary(game_id: str | None = None):
        return {'items': await asyncio.to_thread(vocabulary.list, game_id)}

    @app.get('/v1/vocabulary/export')
    async def export_vocabulary(game_id: str | None = None):
        return Response(await asyncio.to_thread(vocabulary.export, game_id), media_type='text/tab-separated-values; charset=utf-8',
                        headers={'Content-Disposition': 'attachment; filename="dross-vocabulary.tsv"'})

    @app.delete('/v1/vocabulary')
    async def delete_vocabulary():
        return {'deleted': await asyncio.to_thread(vocabulary.delete_all)}

    return app
