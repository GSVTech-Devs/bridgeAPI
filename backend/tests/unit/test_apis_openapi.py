# Parser de OpenAPI/Swagger usado no import do cadastro de API.
from __future__ import annotations

import json

import pytest

from app.domains.apis.openapi import InvalidSpecError, parse_spec, parse_text

OAS3 = {
    "openapi": "3.0.0",
    "info": {"title": "Solver API"},
    "servers": [{"url": "https://api.solver.com/v2"}],
    "paths": {
        "/solve": {
            "post": {
                "summary": "Solve a captcha",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/SolveReq"}
                        }
                    }
                },
            },
            "get": {"summary": "Health"},
        }
    },
    "components": {
        "schemas": {
            "SolveReq": {
                "type": "object",
                "properties": {
                    "site_key": {"type": "string"},
                    "retries": {"type": "integer"},
                    "nested": {"$ref": "#/components/schemas/Nested"},
                },
            },
            "Nested": {"type": "object", "properties": {"flag": {"type": "boolean"}}},
        }
    },
}


def test_parse_extracts_title_and_base_url() -> None:
    out = parse_spec(OAS3)
    assert out["title"] == "Solver API"
    assert out["base_url"] == "https://api.solver.com/v2"


def test_parse_builds_body_template_resolving_refs() -> None:
    out = parse_spec(OAS3)
    post = next(o for o in out["operations"] if o["method"] == "POST")
    body = json.loads(post["request_body_template"])
    assert body == {"site_key": "string", "retries": 0, "nested": {"flag": False}}


def test_get_operation_has_no_body_template() -> None:
    out = parse_spec(OAS3)
    get = next(o for o in out["operations"] if o["method"] == "GET")
    assert get["request_body_template"] is None


def test_parse_swagger2_host_basepath_and_body_param() -> None:
    swagger2 = {
        "swagger": "2.0",
        "info": {"title": "Legacy"},
        "host": "old.api.com",
        "basePath": "/v1",
        "schemes": ["https"],
        "paths": {
            "/query": {
                "post": {
                    "parameters": [
                        {"in": "body", "name": "b", "schema": {
                            "type": "object",
                            "properties": {"q": {"type": "string"}},
                        }}
                    ]
                }
            }
        },
    }
    out = parse_spec(swagger2)
    assert out["base_url"] == "https://old.api.com/v1"
    op = out["operations"][0]
    assert json.loads(op["request_body_template"]) == {"q": "string"}


def test_parse_text_accepts_yaml() -> None:
    yaml_spec = """
openapi: 3.0.0
info:
  title: YAML API
paths:
  /ping:
    post:
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                msg:
                  type: string
"""
    out = parse_text(yaml_spec)
    assert out["title"] == "YAML API"
    assert json.loads(out["operations"][0]["request_body_template"]) == {"msg": "string"}


def test_parse_text_rejects_garbage() -> None:
    with pytest.raises(InvalidSpecError):
        parse_text("not a spec at all")


def test_resolve_handles_circular_ref() -> None:
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/x": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Node"}}
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "Node": {
                    "type": "object",
                    "properties": {"child": {"$ref": "#/components/schemas/Node"}},
                }
            }
        },
    }
    out = parse_spec(spec)  # não deve estourar recursão
    assert out["operations"][0]["request_body_template"] is not None
