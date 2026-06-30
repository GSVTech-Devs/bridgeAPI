# Parser de OpenAPI/Swagger para a documentação do cliente (parse_spec_docs).
from __future__ import annotations

import json

import pytest

from app.domains.apis.openapi import InvalidSpecError, parse_spec_docs, parse_text_docs

OAS3 = {
    "openapi": "3.0.0",
    "info": {"title": "Solver API"},
    "servers": [{"url": "https://api.solver.com/v2"}],
    "paths": {
        "/people/{id}": {
            "parameters": [
                {
                    "name": "id",
                    "in": "path",
                    "required": True,
                    "description": "Identificador",
                    "schema": {"type": "string"},
                }
            ],
            "get": {
                "summary": "Get person",
                "description": "Retorna uma pessoa pelo id.",
                "parameters": [
                    {"name": "fields", "in": "query", "schema": {"type": "string"}}
                ],
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Person"}
                            }
                        },
                    },
                    "404": {"description": "Not found"},
                },
            },
            "post": {
                "summary": "Create person",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Person"}
                        }
                    }
                },
                "responses": {"201": {"description": "Created"}},
            },
        }
    },
    "components": {
        "schemas": {
            "Person": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
            }
        }
    },
}


def test_docs_extract_title_and_base_url() -> None:
    out = parse_spec_docs(OAS3)
    assert out["title"] == "Solver API"
    assert out["base_url"] == "https://api.solver.com/v2"


def test_docs_merges_path_and_operation_parameters() -> None:
    out = parse_spec_docs(OAS3)
    get = next(o for o in out["operations"] if o["method"] == "GET")
    names = {p["name"]: p for p in get["parameters"]}
    assert names["id"]["in"] == "path"
    assert names["id"]["required"] is True
    assert names["id"]["type"] == "string"
    assert names["fields"]["in"] == "query"
    assert names["fields"]["required"] is False


def test_docs_request_example_resolves_refs() -> None:
    out = parse_spec_docs(OAS3)
    post = next(o for o in out["operations"] if o["method"] == "POST")
    assert json.loads(post["request_example"]) == {"name": "string", "age": 0}


def test_docs_get_has_no_request_example() -> None:
    out = parse_spec_docs(OAS3)
    get = next(o for o in out["operations"] if o["method"] == "GET")
    assert get["request_example"] is None


def test_docs_responses_with_example() -> None:
    out = parse_spec_docs(OAS3)
    get = next(o for o in out["operations"] if o["method"] == "GET")
    by_status = {r["status"]: r for r in get["responses"]}
    assert by_status["200"]["description"] == "OK"
    assert json.loads(by_status["200"]["example"]) == {"name": "string", "age": 0}
    assert by_status["404"]["example"] is None


def test_docs_body_parameter_is_not_listed_as_parameter() -> None:
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
                        {
                            "in": "query",
                            "name": "q",
                            "type": "string",
                            "required": True,
                        },
                        {
                            "in": "body",
                            "name": "b",
                            "schema": {
                                "type": "object",
                                "properties": {"x": {"type": "string"}},
                            },
                        },
                    ]
                }
            }
        },
    }
    out = parse_spec_docs(swagger2)
    op = out["operations"][0]
    assert [p["name"] for p in op["parameters"]] == ["q"]
    assert json.loads(op["request_example"]) == {"x": "string"}


def test_parse_text_docs_rejects_garbage() -> None:
    with pytest.raises(InvalidSpecError):
        parse_text_docs("not a spec at all")
