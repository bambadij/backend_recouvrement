from fastapi import Request, status
from fastapi.responses import JSONResponse


class AppException(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND


class BadRequestException(AppException):
    status_code = status.HTTP_400_BAD_REQUEST


class ConflictException(AppException):
    status_code = status.HTTP_409_CONFLICT


class UnauthorizedException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED


class ForbiddenException(AppException):
    status_code = status.HTTP_403_FORBIDDEN


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
