"""Pheonix Unified Console Server: Serves Web UI and proxies management APIs."""

from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

CONSOLE_DIR = Path(__file__).resolve().parent


class OptimizePromptRequest(BaseModel):
    prompt: str
    target_domain: Optional[str] = "general"


def create_console_app() -> FastAPI:
    app = FastAPI(title="Pheonix Unified Intelligence Console", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    def get_index():
        index_file = CONSOLE_DIR / "index.html"
        if not index_file.exists():
            raise HTTPException(status_code=404, detail="index.html not found")
        return FileResponse(index_file)

    @app.get("/styles.css")
    def get_styles():
        return FileResponse(CONSOLE_DIR / "styles.css", media_type="text/css")

    @app.get("/app.js")
    def get_app_js():
        return FileResponse(CONSOLE_DIR / "app.js", media_type="application/javascript")

    @app.get("/manifest.json")
    def get_manifest():
        return FileResponse(CONSOLE_DIR / "manifest.json", media_type="application/json")

    @app.get("/icon.svg")
    def get_icon():
        return FileResponse(CONSOLE_DIR / "icon.svg", media_type="image/svg+xml")

    @app.get("/api/health")
    def get_health():
        return {
            "status": "healthy",
            "modules_total": 36,
            "modules_passing": 36,
            "version": "0.1.0",
        }

    @app.get("/api/tenants")
    def get_tenants():
        return {
            "tenants": [
                {"id": "tenant_enterprise_alpha", "name": "Enterprise Alpha (Prod)", "role": "owner"},
                {"id": "tenant_rnd_beta", "name": "R&D Lab (Staging)", "role": "admin"},
                {"id": "tenant_isolated_demo", "name": "Sandbox Demo", "role": "member"},
            ]
        }

    @app.post("/api/prompt/optimize")
    def optimize_prompt(req: OptimizePromptRequest):
        optimized = (
            f"You are a specialized Pheonix intelligence agent for {req.target_domain}.\n"
            f"Directives: {req.prompt}\n"
            f"Guidelines: Verify citations; enforce sandbox limits; output structured JSON."
        )
        return {
            "original_prompt": req.prompt,
            "optimized_prompt": optimized,
            "domain": req.target_domain,
        }

    return app


app = create_console_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("console.server:app", host="127.0.0.1", port=8080, reload=True)

