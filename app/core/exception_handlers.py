from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Convierte errores de validación de Pydantic en respuestas consistentes."""
    for error in exc.errors():
        field_name = error["loc"][-1] if error["loc"] else None
        error_type = error.get("type")
        error_msg = error.get("msg", "")
        
        # Detectar errores de validación del name (company o user)
        if field_name == "name":
            if "string_too_short" in error_type:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "NAME_TOO_SHORT"}
                )
            elif "string_too_long" in error_type:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "NAME_TOO_LONG"}
                )
        
        # Detectar errores de validación del NIF
        if field_name == "nif":
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "INVALID_NIF_FORMAT"}
            )
        
        # Detectar errores de validación del email
        if field_name == "email":
            if "string_too_long" in error_type:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "EMAIL_TOO_LONG"}
                )
            else:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "INVALID_EMAIL_FORMAT"}
                )
        
        # Detectar errores de validación del username
        if field_name == "username":
            if "string_too_short" in error_type:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "USERNAME_TOO_SHORT"}
                )
            elif "string_too_long" in error_type:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "USERNAME_TOO_LONG"}
                )
            elif "cannot contain spaces" in error_msg:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "USERNAME_CONTAINS_SPACES"}
                )
            elif "can only contain" in error_msg:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "USERNAME_INVALID_CHARACTERS"}
                )
            else:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "INVALID_USERNAME_FORMAT"}
                )
        
        # Detectar errores de validación del password
        if field_name == "password":
            if "string_too_short" in error_type:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "PASSWORD_TOO_SHORT"}
                )
            elif "string_too_long" in error_type:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "PASSWORD_TOO_LONG"}
                )
            else:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "INVALID_PASSWORD_FORMAT"}
                )
    
    # Para otros errores de validación, devolver la respuesta por defecto
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()}
    )
