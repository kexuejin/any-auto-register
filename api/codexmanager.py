"""CodexManager maintenance API."""

from fastapi import APIRouter

router = APIRouter(prefix="/codexmanager", tags=["codexmanager"])


@router.post("/maintain/run")
def maintain_run_now():
    # Import main lazily to avoid circular import at module import time.
    import main as main_mod

    ok, report, err = main_mod.codexmanager_maintainer.try_run_now()
    if not ok:
        return {"ok": False, "error": err or "failed"}

    if report and report.get("error"):
        return {"ok": False, "error": report.get("error")}

    return {"ok": True, "forced": True, "report": report}
