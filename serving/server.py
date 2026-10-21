"""
Pheonix Model Serving REST Server
Exposes HTTP endpoints including /generate for streaming inference with device-profile validation.
"""

from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .core.engine import ModelServingEngine
from .core.resource_limiter import ResourceLimitExceededError


class GenerateRequest(BaseModel):
    model: str = "llama3.2"
    prompt: str
    stream: bool = True
    runtime: Optional[str] = None


def create_serving_app(engine: Optional[ModelServingEngine] = None) -> FastAPI:
    app = FastAPI(title="Pheonix Model Serving Engine", version="0.1.0")
    serving_engine = engine or ModelServingEngine()

    @app.get("/health")
    def health():
        return {
            "status": "healthy",
            "device": {
                "cpu_brand": serving_engine.profile.cpu_brand,
                "total_ram_gb": serving_engine.profile.total_ram_gb,
                "gpu": serving_engine.profile.gpu_name or "CPU",
            },
            "active_runtimes": serving_engine.list_active_runtimes(),
        }

    @app.get("/models")
    def list_models():
        return {"models": [a.model_dump() for a in serving_engine.list_models()]}

    @app.post("/generate")
    def generate(req: GenerateRequest):
        """
        Proxies generation to local runtime (Ollama / Llama.cpp / mock)
        with device-profile checks and optional token streaming.
        """
        try:
            generator = serving_engine.stream_generate(
                model=req.model,
                prompt=req.prompt,
                runtime_name=req.runtime,
            )

            if req.stream:
                def event_stream():
                    for chunk in generator:
                        yield f"{chunk}\n"

                return StreamingResponse(event_stream(), media_type="text/event-stream")
            else:
                full_text = ""
                for chunk in generator:
                    full_text += chunk
                return {"model": req.model, "response": full_text}

        except ResourceLimitExceededError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


app = create_serving_app()
