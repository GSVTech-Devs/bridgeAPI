"""Parser leve de OpenAPI/Swagger para pré-preencher o cadastro de API POST.

Não é um validador completo: extrai `base_url`, título e, por operação, um
`request_body_template` de exemplo (JSON) a partir do schema do request body —
resolvendo `$ref` locais (`#/...`). Suporta OpenAPI 3 e Swagger 2.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

_METHODS = ("get", "post", "put", "patch", "delete")
_MAX_DEPTH = 8


def _resolve(schema: Any, spec: dict, _seen: Optional[set] = None) -> dict:
    """Resolve um `$ref` local; devolve {} para refs externos/inválidos."""
    if not isinstance(schema, dict):
        return {}
    ref = schema.get("$ref")
    if not ref:
        return schema
    if not ref.startswith("#/"):
        return {}
    _seen = _seen or set()
    if ref in _seen:
        return {}
    _seen.add(ref)
    node: Any = spec
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            return {}
        node = node[part]
    return _resolve(node, spec, _seen) if isinstance(node, dict) else {}


def _sample(schema: Any, spec: dict, depth: int = 0) -> Any:
    """Gera um exemplo a partir de um schema JSON (example/default > tipo)."""
    if depth > _MAX_DEPTH:
        return None
    schema = _resolve(schema, spec)
    if not schema:
        return None
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if schema.get("enum"):
        return schema["enum"][0]

    # composições: usa o primeiro ramo
    for key in ("allOf", "oneOf", "anyOf"):
        if isinstance(schema.get(key), list) and schema[key]:
            if key == "allOf":
                merged: dict = {}
                for sub in schema[key]:
                    val = _sample(sub, spec, depth + 1)
                    if isinstance(val, dict):
                        merged.update(val)
                return merged or None
            return _sample(schema[key][0], spec, depth + 1)

    t = schema.get("type")
    if t == "object" or "properties" in schema:
        props = schema.get("properties", {})
        return {k: _sample(v, spec, depth + 1) for k, v in props.items()}
    if t == "array":
        return [_sample(schema.get("items", {}), spec, depth + 1)]
    if t in ("integer", "number"):
        return 0
    if t == "boolean":
        return False
    if t == "string":
        return "string"
    return None


def _request_body_schema(op: dict, spec: dict) -> Any:
    """Schema do corpo da requisição (OpenAPI 3 ou Swagger 2)."""
    # OpenAPI 3: requestBody.content["application/json"].schema
    body = op.get("requestBody")
    if isinstance(body, dict):
        body = _resolve(body, spec)
        content = body.get("content", {})
        for ctype, media in content.items():
            if "json" in ctype and isinstance(media, dict) and "schema" in media:
                return media["schema"]
        if content:  # qualquer content-type com schema
            first = next(iter(content.values()))
            if isinstance(first, dict):
                return first.get("schema")
    # Swagger 2: parameters[in=body].schema
    for param in op.get("parameters", []) or []:
        param = _resolve(param, spec)
        if param.get("in") == "body" and "schema" in param:
            return param["schema"]
    return None


def _base_url(spec: dict) -> Optional[str]:
    servers = spec.get("servers")
    if isinstance(servers, list) and servers and isinstance(servers[0], dict):
        url = servers[0].get("url")
        if url:
            return str(url)
    # Swagger 2
    host = spec.get("host")
    if host:
        scheme = (spec.get("schemes") or ["https"])[0]
        base_path = spec.get("basePath", "") or ""
        return f"{scheme}://{host}{base_path}"
    return None


def parse_spec(spec: dict) -> dict:
    """Extrai título, base_url e operações (com body template) de um spec dict."""
    title = None
    info = spec.get("info")
    if isinstance(info, dict):
        title = info.get("title")

    operations: list[dict] = []
    paths = spec.get("paths") or {}
    if isinstance(paths, dict):
        for path, item in paths.items():
            if not isinstance(item, dict):
                continue
            for method in _METHODS:
                op = item.get(method)
                if not isinstance(op, dict):
                    continue
                schema = _request_body_schema(op, spec)
                body_template = None
                if schema is not None:
                    sample = _sample(schema, spec)
                    if sample is not None:
                        body_template = json.dumps(sample, indent=2, ensure_ascii=False)
                operations.append(
                    {
                        "method": method.upper(),
                        "path": path,
                        "summary": op.get("summary") or op.get("operationId"),
                        "request_body_template": body_template,
                    }
                )

    return {"title": title, "base_url": _base_url(spec), "operations": operations}


def _param_type(param: dict, spec: dict) -> Optional[str]:
    """Tipo declarado de um parâmetro (OpenAPI 3 usa `schema`, Swagger 2 inline)."""
    schema = param.get("schema")
    if isinstance(schema, dict):
        schema = _resolve(schema, spec)
        t = schema.get("type")
        if t:
            return str(t)
    t = param.get("type")  # Swagger 2
    return str(t) if t else None


def _parameters(op: dict, item: dict, spec: dict) -> list[dict]:
    """Parâmetros de path/query/header da operação (mescla nível path + operação).

    Ignora `in=body` (vira request_example). Resolve `$ref`. Mantém a ordem.
    """
    raw: list = []
    raw.extend(item.get("parameters", []) or [])  # parâmetros comuns ao path
    raw.extend(op.get("parameters", []) or [])
    out: list[dict] = []
    seen: set = set()
    for param in raw:
        param = _resolve(param, spec)
        if not isinstance(param, dict):
            continue
        location = param.get("in")
        if location == "body":  # corpo (Swagger 2) → tratado como request_example
            continue
        name = param.get("name")
        if not name:
            continue
        key = (name, location)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "name": str(name),
                "in": str(location) if location else None,
                "required": bool(param.get("required", False)),
                "description": param.get("description"),
                "type": _param_type(param, spec),
                "example": param.get("example"),
            }
        )
    return out


def _responses(op: dict, spec: dict) -> list[dict]:
    """Lista de respostas {status, description, example?} da operação."""
    responses = op.get("responses")
    if not isinstance(responses, dict):
        return []
    out: list[dict] = []
    for status_code, resp in responses.items():
        resp = _resolve(resp, spec) if isinstance(resp, dict) else {}
        example = None
        content = resp.get("content")
        if isinstance(content, dict):
            for ctype, media in content.items():
                if "json" in ctype and isinstance(media, dict) and "schema" in media:
                    sample = _sample(media["schema"], spec)
                    if sample is not None:
                        example = json.dumps(sample, indent=2, ensure_ascii=False)
                    break
        out.append(
            {
                "status": str(status_code),
                "description": resp.get("description"),
                "example": example,
            }
        )
    return out


def parse_spec_docs(spec: dict) -> dict:
    """Extrai título e operações ricas (params, exemplo de body, respostas) do spec.

    Diferente de ``parse_spec`` (usado no import de rascunhos), aqui o foco é a
    documentação do cliente: cada operação carrega o que renderiza a doc.
    """
    title = None
    info = spec.get("info")
    if isinstance(info, dict):
        title = info.get("title")

    operations: list[dict] = []
    paths = spec.get("paths") or {}
    if isinstance(paths, dict):
        for path, item in paths.items():
            if not isinstance(item, dict):
                continue
            for method in _METHODS:
                op = item.get(method)
                if not isinstance(op, dict):
                    continue
                schema = _request_body_schema(op, spec)
                request_example = None
                if schema is not None:
                    sample = _sample(schema, spec)
                    if sample is not None:
                        request_example = json.dumps(
                            sample, indent=2, ensure_ascii=False
                        )
                operations.append(
                    {
                        "method": method.upper(),
                        "path": path,
                        "summary": op.get("summary") or op.get("operationId"),
                        "description": op.get("description"),
                        "parameters": _parameters(op, item, spec),
                        "request_example": request_example,
                        "responses": _responses(op, spec),
                    }
                )

    return {"title": title, "base_url": _base_url(spec), "operations": operations}


class InvalidSpecError(Exception):
    pass


def _load_doc(text: str) -> dict:
    """Carrega o documento OpenAPI/Swagger (JSON ou YAML) e valida que parece um."""
    text = (text or "").strip()
    if not text:
        raise InvalidSpecError("Spec vazio")
    doc: Any = None
    try:
        doc = json.loads(text)
    except Exception:
        try:
            import yaml

            doc = yaml.safe_load(text)
        except Exception as exc:  # noqa: BLE001
            raise InvalidSpecError(
                f"Não foi possível parsear como JSON nem YAML: {exc}"
            )
    if not isinstance(doc, dict) or (
        "paths" not in doc and "swagger" not in doc and "openapi" not in doc
    ):
        raise InvalidSpecError("Documento não parece um OpenAPI/Swagger válido")
    return doc


def parse_text(text: str) -> dict:
    """Aceita JSON ou YAML colado e devolve ``parse_spec`` do documento."""
    return parse_spec(_load_doc(text))


def parse_text_docs(text: str) -> dict:
    """Aceita JSON ou YAML colado e devolve ``parse_spec_docs`` do documento."""
    return parse_spec_docs(_load_doc(text))


async def fetch_spec(url: str, *, timeout: float = 15.0) -> dict:
    """Busca o spec na URL da doc (ex.: ``/openapi.json``) e devolve ``parse_spec``.

    Faz o fetch no servidor (evita CORS no front). Aceita só http(s); o corpo pode
    ser JSON ou YAML (delegado a ``parse_text``). Erros viram ``InvalidSpecError``.
    """
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https"):
        raise InvalidSpecError("A URL deve começar com http:// ou https://")
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={
                    "Accept": "application/json, application/yaml, text/yaml, */*"
                },
            )
            resp.raise_for_status()
            text = resp.text
    except InvalidSpecError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise InvalidSpecError(f"Não foi possível buscar o spec na URL: {exc}")
    return parse_text(text)


async def fetch_spec_docs(
    url: str, *, timeout: float = 15.0, auth_headers: Optional[dict] = None
) -> dict:
    """Como ``fetch_spec``, mas devolve ``parse_spec_docs`` (doc rica do cliente).

    ``auth_headers`` injeta a credencial da API (ex.: ``x-api-key`` / ``Bearer``)
    quando o ``openapi.json`` da API externa é protegido — mesma master key usada
    no proxy. Não duplica o ``Accept``.
    """
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https"):
        raise InvalidSpecError("A URL deve começar com http:// ou https://")
    headers = {"Accept": "application/json, application/yaml, text/yaml, */*"}
    if auth_headers:
        headers.update(auth_headers)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            text = resp.text
    except InvalidSpecError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise InvalidSpecError(f"Não foi possível buscar o spec na URL: {exc}")
    return parse_text_docs(text)
