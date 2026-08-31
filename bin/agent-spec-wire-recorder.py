#!/usr/bin/env python3
"""Record the real size of every prompt Claude Code sends.

Claude Code's own usage numbers are worthless through a local proxy: the same
session reports input_tokens 8194 for a 200-token prompt and for a 9,000-token
one, because the value never comes from the model. Measuring context volume
therefore has to happen on the wire.

This sits between Claude Code and litellm, forwards everything untouched, and
appends one JSON line per request with the exact byte size of the request body
and the number of messages in it. Responses stream through unmodified.

    ./context-recorder.py --listen 4002 --upstream http://127.0.0.1:4001 \
                          --log requests.jsonl
"""
import argparse, json, os, time

import httpx
from starlette.applications import Starlette
from starlette.responses import StreamingResponse, Response
from starlette.routing import Route
import uvicorn

ap = argparse.ArgumentParser()
ap.add_argument("--listen", type=int, default=4002)
ap.add_argument("--upstream", default="http://127.0.0.1:4001")
ap.add_argument("--log", default="requests.jsonl")
args = ap.parse_args()

client = httpx.AsyncClient(base_url=args.upstream, timeout=None)


def record(path, body):
    n_messages = n_system = 0
    try:
        payload = json.loads(body)
        n_messages = len(payload.get("messages") or [])
        system = payload.get("system")
        if isinstance(system, list):
            n_system = sum(len(json.dumps(b)) for b in system)
        elif isinstance(system, str):
            n_system = len(system)
    except Exception:
        pass
    with open(args.log, "a") as fh:
        fh.write(json.dumps({
            "t": time.time(),
            "path": path,
            "request_bytes": len(body),
            "system_bytes": n_system,
            "messages": n_messages,
        }) + "\n")


async def proxy(request):
    body = await request.body()
    record(request.url.path, body)
    headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
    req = client.build_request(request.method, request.url.path, content=body,
                               headers=headers, params=request.query_params)
    upstream = await client.send(req, stream=True)
    if "text/event-stream" in upstream.headers.get("content-type", ""):
        async def body_iter():
            async for chunk in upstream.aiter_raw():
                yield chunk
            await upstream.aclose()
        return StreamingResponse(body_iter(), status_code=upstream.status_code,
                                 headers={k: v for k, v in upstream.headers.items()
                                          if k.lower() not in ("content-length", "content-encoding")})
    data = await upstream.aread()
    await upstream.aclose()
    return Response(content=data, status_code=upstream.status_code,
                    headers={k: v for k, v in upstream.headers.items()
                             if k.lower() not in ("content-length", "content-encoding")})


app = Starlette(routes=[Route("/{path:path}", proxy, methods=["GET", "POST", "PUT", "DELETE"])])
uvicorn.run(app, host="127.0.0.1", port=args.listen, log_level="warning")
