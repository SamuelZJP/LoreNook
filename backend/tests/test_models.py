from backend.tests.state_fixtures import STATE_SCHEMA
from copy import deepcopy
import json

import httpx
import pytest

from backend.llm.client import ModelClient
from backend.llm.parameters import merge_parameters
from backend.modules.models.service import ModelService
from backend.repository.models import Chat, ChatModelBinding, ModelConfig
from backend.repository.queries import Repository
from backend.schemas.models import ModelConnection
from backend.schemas.presets import BuiltRequest
from backend.shared.errors import ConflictError, ModelCallError, ModelConfigurationError
from backend.tests.test_catalog_api import run_api

API = "google_generate_content"
BODY = {"contents": [{"role": "user", "parts": [{"text": " 原文\r\n"}]}]}
RESULT = {"candidates": [{"content": {"parts": [{"functionCall": {
    "name": "game_content", "args": {"content": "<content>正文</content>"}
}}]}, "finishReason": "STOP"}], "usageMetadata": {"totalTokenCount": 123}}


def connection(**values):
    return ModelConnection(**{
        "api_type": API, "base_url": "https://provider.test/v1beta/",
        "api_key": "private-test-key", "model": "example-model", **values,
    })


def config_payload(**values):
    return {"name": "模型", "api_type": API, "base_url": "https://provider.test/v1beta",
            "model": "example-model", "api_key": "private-test-key", **values}


@pytest.fixture
def make_client():
    clients = []
    def create(handler, **options):
        client = ModelClient(transport=httpx.MockTransport(handler), **options)
        clients.append(client)
        return client
    yield create
    for client in clients:
        client.close()


def test_recursive_merge_explicit_values_and_no_shared_references():
    defaults = {"generationConfig": {"temperature": 0.5, "topP": 0.8, "stopSequences": ["旧"]},
                "safetySettings": [{"category": "默认"}]}
    explicit = {"generationConfig": {"temperature": 0, "stopSequences": [], "topP": None},
                "safetySettings": []}
    before = deepcopy((defaults, explicit))
    merged = merge_parameters(defaults, explicit)
    assert merged == {"generationConfig": {"temperature": 0, "topP": None, "stopSequences": []},
                      "safetySettings": []}
    merged["generationConfig"]["stopSequences"].append("只修改副本")
    assert (defaults, explicit) == before
    assert merge_parameters({"a": {"b": 1}}, {"a": {}}) == {"a": {"b": 1}}


def test_google_request_authentication_merge_and_full_json_response(make_client):
    seen = []
    def handler(request):
        seen.append(request)
        assert str(request.url) == "https://provider.test/v1beta/models/example-model:generateContent"
        assert request.method == "POST"
        assert request.headers["x-goog-api-key"] == "private-test-key"
        assert request.headers["content-type"] == "application/json"
        assert "private-test-key" not in str(request.url)
        body = json.loads(request.content)
        assert body["contents"] == BODY["contents"]
        assert body["generationConfig"] == {"temperature": 1, "topP": 0.9, "seed": None}
        assert request.extensions["timeout"] == {"connect": 10, "read": 300, "write": 30, "pool": 5}
        return httpx.Response(200, json=RESULT)
    config = connection(default_parameters={"generationConfig": {"temperature": 0.5, "topP": 0.9}})
    built = BuiltRequest(api_type=API, body={**BODY, "generationConfig": {"temperature": 1, "seed": None}})
    before = deepcopy((config.model_dump(), built.model_dump()))
    result = make_client(handler).invoke(config, built)
    assert result.response == RESULT and len(seen) == 1
    assert (config.model_dump(), built.model_dump()) == before


def test_explicit_model_overrides_connection_and_optional_key(make_client):
    def handler(request):
        assert request.url.path == "/custom/v1/models/override:generateContent"
        assert "model" not in json.loads(request.content)
        assert "x-goog-api-key" not in request.headers
        return httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
    result = make_client(handler).invoke(
        connection(base_url="http://localhost/custom/v1", api_key=""),
        BuiltRequest(api_type=API, body={**BODY, "model": "models/override"}),
    )
    assert result.response["promptFeedback"]["blockReason"] == "SAFETY"  # preset decides acceptance


@pytest.mark.parametrize("config_values,body,api_type", [
    ({}, BODY, "incompatible"), ({"api_type": "unknown"}, BODY, "unknown"),
    ({}, {}, API), ({}, {"contents": []}, API), ({}, {"contents": "wrong"}, API),
    ({"model": "../escape"}, BODY, API), ({}, {**BODY, "model": None}, API),
    ({"base_url": "ftp://provider.test/v1beta"}, BODY, API),
    ({"base_url": "https://user:password@provider.test/v1beta"}, BODY, API),
    ({"base_url": "https://provider.test/v1beta?"}, BODY, API),
    ({"api_key": "bad\r\nheader"}, BODY, API),
    ({"api_key": "中文"}, BODY, API), ({}, {**BODY, "value": float("nan")}, API),
])
def test_invalid_configuration_fails_before_network(make_client, config_values, body, api_type):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={})
    with pytest.raises(ModelConfigurationError):
        make_client(handler).invoke(connection(**config_values), BuiltRequest(api_type=api_type, body=body))
    assert calls == []


@pytest.mark.parametrize("status", [301, 302, 400, 401, 403, 429, 500, 503])
def test_http_errors_are_sanitized_without_redirects_or_retries(make_client, status):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(status, headers={"location": "https://other.test/collect"},
                              json={"error": "private-test-key provider-internals"})
    with pytest.raises(ModelCallError) as error:
        make_client(handler).invoke(connection(), BuiltRequest(api_type=API, body=BODY))
    assert error.value.kind == "http" and error.value.upstream_status == status
    assert "private-test-key" not in str(error.value) and "provider-internals" not in str(error.value)
    assert len(seen) == 1


@pytest.mark.parametrize("failure,kind", [
    (httpx.ConnectTimeout, "timeout"), (httpx.ReadTimeout, "timeout"),
    (httpx.ConnectError, "network"), (httpx.ReadError, "network"),
    (httpx.RemoteProtocolError, "network"), (httpx.DecodingError, "network"),
])
def test_transport_error_classification(make_client, failure, kind):
    seen = []
    def handler(request):
        seen.append(request)
        raise failure("private-test-key URL with credentials", request=request)
    with pytest.raises(ModelCallError) as error:
        make_client(handler).invoke(connection(), BuiltRequest(api_type=API, body=BODY))
    assert error.value.kind == kind and "private-test-key" not in str(error.value)
    assert len(seen) == 1


@pytest.mark.parametrize("raw", [b"not-json", b"[]", b"null", b"42", b'{"x":NaN}', b'{"x":1e999}',
                                   b'{"x":"\\ud800"}'])
def test_invalid_response_json(make_client, raw):
    with pytest.raises(ModelCallError) as error:
        make_client(lambda request: httpx.Response(200, content=raw)).invoke(
            connection(), BuiltRequest(api_type=API, body=BODY))
    assert error.value.kind == "invalid_response"


def test_response_size_and_provider_error(make_client):
    with pytest.raises(ModelCallError) as error:
        make_client(lambda request: httpx.Response(200, json={"text": "x" * 100}), max_response_bytes=50).invoke(
            connection(), BuiltRequest(api_type=API, body=BODY))
    assert error.value.kind == "response_too_large"
    with pytest.raises(ModelCallError) as error:
        make_client(lambda request: httpx.Response(200, json={"error": "private-test-key"})).invoke(
            connection(), BuiltRequest(api_type=API, body=BODY))
    assert error.value.kind == "provider" and "private-test-key" not in str(error.value)


@pytest.mark.parametrize("scope", ["source", "chat"])
def test_config_api_crud_scope_secrets_and_invocation(database, chat, scope):
    root = "/api/model-configs" if scope == "source" else f"/api/chats/{chat[0]}/model-configs"
    other_root = f"/api/chats/{chat[0]}/model-configs" if scope == "source" else "/api/model-configs"
    calls = []
    def handler(request):
        calls.append(request)
        # Confirm the database read transaction ended before network I/O.
        with database.transaction() as session:
            Repository(session).get(Chat, chat[0]).title = "网络期间可写入"
        return httpx.Response(200, json=RESULT)
    async def scenario(client):
        assert (await client.get(root)).json() == []
        created = await client.post(root, json=config_payload(default_parameters={"generationConfig": {"temperature": 0.5}}))
        assert created.status_code == 201, created.text
        item = created.json()
        assert item["has_api_key"] is True and "api_key" not in item and "private-test-key" not in created.text
        assert item["chat_id"] == (None if scope == "source" else chat[0])
        path = root + "/" + item["id"]
        assert (await client.get(path)).json() == item
        assert (await client.patch(path, json={})).json() == item
        assert (await client.patch(path, json={"name": "改名"})).json()["has_api_key"] is True
        assert item["timeout_seconds"] == 300 and item["streaming"] is False
        assert (await client.patch(path, json={"streaming": True})).json()["streaming"] is True
        assert (await client.patch(path, json={"streaming": False})).json()["streaming"] is False
        assert (await client.patch(path, json={"timeout_seconds": 600})).json()["timeout_seconds"] == 600
        for bad in ({"name": " "}, {"api_key": None}, {"base_url": None}, {"model": " "},
                    {"default_parameters": []}, {"chat_id": chat[0]}, {"base_url": "ftp://bad"},
                    {"timeout_seconds": None}, {"streaming": None}, {"streaming": "yes"}, {"timeout_seconds": 9}, {"timeout_seconds": 1801}, {"timeout_seconds": 60.5}):
            assert (await client.patch(path, json=bad)).status_code == 422
        foreign = (await client.post(other_root, json=config_payload())).json()
        foreign_path = root + "/" + foreign["id"]
        for method in ("GET", "PATCH", "DELETE"):
            result = await client.request(method, foreign_path, **({"json": {}} if method == "PATCH" else {}))
            assert result.status_code == 404
        assert (await client.post(foreign_path + "/invoke", json={"api_type": API, "body": BODY})).status_code == 404
        assert (await client.post(path + "/invoke", json={"api_type": "wrong", "body": BODY})).status_code == 422
        assert calls == []
        result = await client.post(path + "/invoke", json={"api_type": API, "body": BODY})
        assert result.status_code == 200, result.text
        assert result.json() == {"response": RESULT} and len(calls) == 1
        assert calls[0].extensions["timeout"]["read"] == 600
        assert (await client.patch(path, json={"api_key": ""})).json()["has_api_key"] is False
        assert (await client.patch(path, json={"api_key": "new-key"})).json()["has_api_key"] is True
        assert (await client.delete(path)).status_code == 204
        assert (await client.get(path)).status_code == 404
        assert (await client.get("/api/chats/missing/model-configs")).status_code == 404
        docs = (await client.get("/openapi.json")).json()
        endpoint = docs["paths"]["/api/chats/{chat_id}/model-configs/{config_id}/invoke"]["post"]
        assert {p["name"] for p in endpoint["parameters"] if p["in"] == "path"} == {"chat_id", "config_id"}
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("failure,status,kind", [
    ("timeout", 504, "timeout"), ("network", 502, "network"),
    ("http", 502, "http"), ("json", 502, "invalid_response"),
])
def test_http_call_errors_do_not_expose_credentials(database, failure, status, kind):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("private-test-key", request=request)
        if failure == "network":
            raise httpx.ConnectError("private-test-key", request=request)
        return httpx.Response(401 if failure == "http" else 200, content=b"private-test-key")
    async def scenario(client):
        created = (await client.post("/api/model-configs", json=config_payload())).json()
        response = await client.post(f"/api/model-configs/{created['id']}/invoke", json={"api_type": API, "body": BODY})
        assert response.status_code == status
        assert response.json()["detail"]["kind"] == kind
        assert "private-test-key" not in response.text
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))


def test_model_copy_bindings_deletion_and_detached_connection(database, chat):
    with database.transaction() as session:
        repo = Repository(session)
        config = repo.add(ModelConfig(chat_id=chat[0], **config_payload(default_parameters={"nested": {"v": 1}})))
        config_id = config.id
        for purpose in ("writing", "state_update"):
            repo.add(ChatModelBinding(chat_id=chat[0], purpose=purpose, model_config_id=config_id))
    with database.read() as session:
        service = ModelService(Repository(session), chat[0])
        selected = service.for_purpose("writing")
        assert selected == service.for_purpose("state_update")
        with pytest.raises(ConflictError):
            service.for_purpose("episode_summary")
    assert selected.api_key.get_secret_value() == "private-test-key"
    selected.default_parameters["nested"]["v"] = 100
    with database.read() as session:
        assert Repository(session).get(ModelConfig, config_id).default_parameters["nested"]["v"] == 1
    async def scenario(client):
        root = f"/api/chats/{chat[0]}"
        assert (await client.get(root)).json()["model_configs"][0]["has_api_key"] is True
        assert (await client.delete(root + f"/model-configs/{config_id}")).status_code == 204
        assert (await client.get(root)).json()["model_bindings"] == {}
    run_api(database, scenario)


def test_source_model_copy_independence_and_cross_chat_access(database):
    async def scenario(client):
        source = (await client.post("/api/model-configs", json=config_payload(timeout_seconds=900, streaming=True))).json()
        character = (await client.post("/api/characters", json={"name": "角色", "state_schema": STATE_SCHEMA})).json()
        identity = (await client.post("/api/user-identities", json={"name": "身份"})).json()
        payload = {"title": "聊天", "character_id": character["id"], "user_identity_id": identity["id"],
                   "model_bindings": {"writing": source["id"], "state_update": source["id"]}}
        first = (await client.post("/api/chats", json=payload)).json()
        second = (await client.post("/api/chats", json=payload)).json()
        assert len(first["model_configs"]) == 1 and first["model_configs"][0]["timeout_seconds"] == 900
        assert first["model_configs"][0]["streaming"] is True
        assert first["model_bindings"]["writing"] == first["model_bindings"]["state_update"]
        first_id, second_id = first["model_configs"][0]["id"], second["model_configs"][0]["id"]
        assert len({first_id, second_id, source["id"]}) == 3
        first_path = f"/api/chats/{first['id']}/model-configs/{first_id}"
        second_path = f"/api/chats/{second['id']}/model-configs/{second_id}"
        assert (await client.patch(first_path, json={"api_key": "", "model": "changed"})).status_code == 200
        assert (await client.get(second_path)).json()["has_api_key"] is True
        assert (await client.get(second_path)).json()["model"] == "example-model"
        assert (await client.get(f"/api/chats/{second['id']}/model-configs/{first_id}")).status_code == 404
        assert (await client.get(f"/api/model-configs/{first_id}?chat_id={first['id']}")).status_code == 404
        assert (await client.delete(f"/api/model-configs/{source['id']}")).status_code == 204
        assert (await client.get(second_path)).status_code == 200
    run_api(database, scenario)


def test_invalid_configuration_input_does_not_echo_api_key(database, chat):
    async def scenario(client):
        created = (await client.post("/api/model-configs", json=config_payload())).json()
        # PATCH's null-field check reports the whole object unless input is omitted.
        invalid = await client.patch(f"/api/model-configs/{created['id']}",
                                     json={"api_key": "private-test-key", "name": None})
        assert invalid.status_code == 422 and "private-test-key" not in invalid.text
        invalid = await client.post("/api/model-configs", json=config_payload(api_key={"unexpected": "private-test-key"}))
        assert invalid.status_code == 422 and "private-test-key" not in invalid.text
        invalid = await client.post("/api/model-configs", json=config_payload(api_key="private-test-key", model=None))
        assert invalid.status_code == 422 and "private-test-key" not in invalid.text
    run_api(database, scenario)
