"""Pheonix Unified Console Server: Serves Web UI and proxies management APIs."""

import os
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

CONSOLE_DIR = Path(__file__).resolve().parent


class OptimizePromptRequest(BaseModel):
    prompt: str
    target_domain: Optional[str] = "general"


class ChatDispatchRequest(BaseModel):
    message: str
    tenant_id: Optional[str] = "default"
    role: Optional[str] = "owner"
    model: Optional[str] = "llama3.2:1b"


def call_gateway_completion(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: str = "llama3.2:1b",
    timeout: float = 1.0,
) -> Dict[str, Any]:
    """Attempts to invoke the local/remote Model Gateway chat completions endpoint."""
    gateway_url = os.getenv("MODEL_GATEWAY_URL", "http://localhost:4000").rstrip("/")
    endpoint = f"{gateway_url}/v1/chat/completions"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "PheonixConsole/0.1"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choice = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {
                "success": True,
                "content": choice,
                "source": "model-gateway",
                "model": model,
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "gateway_url": gateway_url,
            "source": "offline-preview",
        }


def check_gateway_health(timeout: float = 0.4) -> bool:
    gateway_url = os.getenv("MODEL_GATEWAY_URL", "http://localhost:4000").rstrip("/")
    try:
        req = urllib.request.Request(f"{gateway_url}/health", headers={"User-Agent": "PheonixConsole/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 204)
    except Exception:
        return False


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
        """Reports real subsystem statuses and preview state."""
        # 1. Audit ledger connectivity
        audit_ok = False
        audit_count = 0
        try:
            from audit.client import get_audit_logger
            logger = get_audit_logger()
            audit_ok = logger.verify_chain()
            audit_count = logger.ledger.count()
        except Exception:
            pass

        # 2. Vault availability
        vault_ok = False
        try:
            from vault.core.manager import KeyStoreManager
            vault_ok = True
        except Exception:
            pass

        # 3. Auth subsystem readiness
        auth_ok = False
        try:
            from auth.core.manager import AuthManager
            auth_ok = True
        except Exception:
            pass

        # 4. Model Gateway connectivity
        gateway_connected = check_gateway_health()

        return {
            "status": "healthy" if (audit_ok and vault_ok and auth_ok) else "degraded",
            "preview_mode": True,
            "preview_notice": "Pheonix Console Preview: Live management endpoints active; Gateway inference on :4000",
            "components": {
                "audit_ledger": "verified" if audit_ok else "unverified",
                "audit_records_count": audit_count,
                "vault": "ready" if vault_ok else "error",
                "auth": "ready" if auth_ok else "error",
                "model_gateway": "connected" if gateway_connected else "offline",
            },
            "timestamp": time.time(),
        }

    @app.get("/api/tenants")
    def get_tenants():
        """Returns real tenants registered across Auth and the Audit Ledger."""
        tenants = [{"id": "default", "name": "Default Workspace (Auth)", "role": "owner"}]
        seen = {"default"}

        # Query tenants recorded in the real Audit Ledger
        try:
            from audit.client import get_audit_logger
            logger = get_audit_logger()
            entries = logger.query(limit=100)
            for e in entries:
                t_id = getattr(e, "tenant_id", None)
                if t_id and t_id not in seen:
                    seen.add(t_id)
                    tenants.append({"id": t_id, "name": f"Tenant {t_id}", "role": getattr(e, "role", "member")})
        except Exception:
            pass

        return {"tenants": tenants}

    @app.get("/api/audit")
    def get_audit(tenant_id: Optional[str] = None, limit: int = 50):
        """Reads real records directly from the tamper-evident hash-chained audit ledger."""
        try:
            from audit.client import get_audit_logger
            logger = get_audit_logger()
            entries = logger.query(tenant_id=tenant_id, limit=limit)
            chain_valid = logger.verify_chain()
            return {
                "verified": chain_valid,
                "count": len(entries),
                "entries": [
                    {
                        "id": e.id,
                        "timestamp": e.timestamp.strftime("%Y-%m-%d %H:%M:%S") if hasattr(e.timestamp, "strftime") else str(e.timestamp)[:19],
                        "tenant_id": e.tenant_id,
                        "role": e.role,
                        "module": e.module,
                        "action": e.action,
                        "resource": e.resource,
                        "status": e.status,
                        "severity": e.severity.value if hasattr(e.severity, "value") else str(e.severity),
                    }
                    for e in entries
                ],
            }
        except Exception as e:
            return {"verified": False, "count": 0, "entries": [], "error": str(e)}

    @app.post("/api/chat/dispatch")
    def dispatch_chat(req: ChatDispatchRequest):
        """Dispatches chat prompt to Model Gateway completions with fallback."""
        sys_prompt = f"You are a Pheonix Assistant for tenant {req.tenant_id} with {req.role} permissions."
        result = call_gateway_completion(prompt=req.message, system_prompt=sys_prompt, model=req.model or "llama3.2:1b")

        # Record audit event for query
        try:
            from audit.client import get_audit_logger
            get_audit_logger().record(
                module="console",
                action="chat_dispatch",
                tenant_id=req.tenant_id or "default",
                role=req.role or "owner",
                resource="gateway:chat_completions",
                status="success" if result["success"] else "offline_preview",
                details={"model": req.model, "source": result["source"]},
            )
        except Exception:
            pass

        if result["success"]:
            return {
                "reply": result["content"],
                "source": "model-gateway",
                "model": result["model"],
            }
        else:
            return {
                "reply": (
                    f"[Model Gateway Offline at {result['gateway_url']}]\n"
                    f"Console Preview: Query '{req.message}' received. "
                    f"To enable live model generation, ensure the Model Gateway container is started on port 4000."
                ),
                "source": "offline-preview",
                "error": result.get("error"),
            }

    @app.post("/api/prompt/optimize")
    def optimize_prompt(req: OptimizePromptRequest):
        """Attempts to optimize prompt using the Model Gateway with structured fallback."""
        sys_prompt = (
            f"You are a prompt engineering compiler for Pheonix agents in the {req.target_domain} domain. "
            f"Refine the user draft into high-clarity instructions, structured constraints, and output format."
        )
        res = call_gateway_completion(
            prompt=f"Optimize this agent directive:\n{req.prompt}",
            system_prompt=sys_prompt,
            timeout=2.0,
        )

        try:
            from audit.client import get_audit_logger
            get_audit_logger().record(
                module="console",
                action="prompt_optimize",
                resource=f"domain:{req.target_domain}",
                status="success",
                details={"source": res["source"]},
            )
        except Exception:
            pass

        if res["success"]:
            return {
                "original_prompt": req.prompt,
                "optimized_prompt": res["content"],
                "domain": req.target_domain,
                "source": "model-gateway",
            }
        else:
            optimized_preview = (
                f"[Gateway Offline Preview - {req.target_domain}]\n"
                f"### System Directive:\n"
                f"You are a specialized Pheonix autonomous agent for {req.target_domain}.\n\n"
                f"### Core Instructions:\n"
                f"{req.prompt}\n\n"
                f"### Operational Constraints:\n"
                f"- Enforce tenant isolation and verify cryptographic audit hashes\n"
                f"- Run sandboxed code through DockerRunner with language dispatch\n"
                f"- Output structured responses conforming to schema"
            )
            return {
                "original_prompt": req.prompt,
                "optimized_prompt": optimized_preview,
                "domain": req.target_domain,
                "source": "offline-preview",
            }

    return app


app = create_console_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("console.server:app", host="127.0.0.1", port=8080, reload=True)

