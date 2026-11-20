"""授权接口：无授权时也允许查看、导出申请与导入续期。"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from .license_core import LicenseDenied, LicenseError


class ImportBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    content: str = Field(min_length=1, max_length=32768)


def denial_content(exc: LicenseDenied) -> dict:
    return {"detail": str(exc), "code": "LICENSE_" + exc.status["state"].upper(),
            "license": exc.status}


def license_router(service) -> APIRouter:
    router = APIRouter(prefix="/api/license", tags=["license"])

    @router.get("/status")
    def status():
        return service.status()

    @router.get("/request")
    def request():
        try:
            data = service.export_request()
        except LicenseError as exc:
            raise HTTPException(503, "无法生成机器申请文件，请检查本机机器标识") from exc
        return Response(data, media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="client_id"',
                                 "Cache-Control": "no-store"})

    @router.post("/import")
    def import_license(body: ImportBody):
        data = body.content.encode("utf-8")
        if len(data) > 32768:
            raise HTTPException(413, "授权文件超过 32 KiB")
        try:
            result = service.import_license(data)
            if not result["allowedToStart"]:
                raise HTTPException(400, detail=denial_content(LicenseDenied(result)))
            return result
        except LicenseDenied as exc:
            raise HTTPException(400, detail=denial_content(exc)) from exc
        except LicenseError as exc:
            raise HTTPException(400, "授权文件校验失败，原授权未替换") from exc

    return router
