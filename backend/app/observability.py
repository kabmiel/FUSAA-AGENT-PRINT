import json
import logging
import time
import uuid
import re
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class JsonFormatter(logging.Formatter):
    def format(self,record):return json.dumps({"timestamp":self.formatTime(record),"level":record.levelname,"logger":record.name,"message":record.getMessage()})

class RedactSessionSecrets(logging.Filter):
    def filter(self,record):
        record.msg=re.sub(r'([?&](?:token|key|hub\.verify_token)=)[^&\s"\x27]+',r'\1[REDACTED]',record.getMessage())
        record.args=()
        return True

def configure_logging(level:str):
    handler=logging.StreamHandler();handler.setFormatter(JsonFormatter());root=logging.getLogger();root.handlers=[handler];root.setLevel(level.upper())
    for logger in (root,logging.getLogger("uvicorn"),logging.getLogger("uvicorn.error"),logging.getLogger("uvicorn.access")):
        for item in logger.handlers:item.addFilter(RedactSessionSecrets())

class RequestAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request:Request,call_next):
        request_id=request.headers.get("X-Request-ID",str(uuid.uuid4()));started=time.perf_counter()
        response=await call_next(request);response.headers["X-Request-ID"]=request_id
        logging.getLogger("fusaa.http").info(json.dumps({"request_id":request_id,"method":request.method,"path":request.url.path,"status":response.status_code,"duration_ms":round((time.perf_counter()-started)*1000,2)}))
        return response
