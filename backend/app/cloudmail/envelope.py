"""cloud-mail 兼容层：返回包格式 {code, message, data}，HTTP 始终 200。

cloud-mail 前端的 axios 拦截器只看 body 里的 code：
  200 成功；401 跳登录；403 警告；502 报错弹 HTML；其他弹 message。
"""
import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

log = logging.getLogger("cloudmail")


def ok(data=None):
    return {"code": 200, "message": "success", "data": data}


def fail(message: str, code: int = 500):
    return {"code": code, "message": message or "服务器错误", "data": None}


class CMFail(Exception):
    """业务异常，转为 fail 包。"""

    def __init__(self, message: str, code: int = 500):
        super().__init__(message)
        self.message = message
        self.code = code


class CMRoute(APIRoute):
    """把返回值包成 ok(...)/CMFail 转成 fail(...)，HTTP 始终 200。"""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def cm_handler(request: Request):
            try:
                result = await original(request)
                # 端点应返回 ok(...)；若返回了裸值也包一层
                if isinstance(result, JSONResponse):
                    return result
                if isinstance(result, dict) and "code" in result:
                    return JSONResponse(result)
                return JSONResponse(ok(result))
            except CMFail as e:
                return JSONResponse(fail(e.message, e.code))
            except RequestValidationError:
                return JSONResponse(fail("请求参数错误", 400))
            except Exception as e:  # noqa: BLE001
                log.exception("cloudmail shim error")
                return JSONResponse(fail(f"服务器错误：{type(e).__name__}"))

        return cm_handler
