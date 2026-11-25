import httpx
import pytest

from backend.llm.address_guard import PublicAddressTransport, is_public, parse_networks
from backend.shared.errors import ModelConfigurationError
from backend.shared.scope import scoped, user_scope


@pytest.mark.parametrize("address, public", [
    ("8.8.8.8", True), ("2606:4700::1111", True), ("127.0.0.1", False), ("10.1.2.3", False),
    ("192.168.31.64", False), ("172.16.0.1", False), ("169.254.169.254", False), ("100.64.0.1", False),
    ("0.0.0.0", False), ("::1", False), ("fe80::1%eth0", False), ("fd00::1", False), ("::ffff:127.0.0.1", False),
    ("224.0.0.1", False),
])
def test_public_addresses(address, public):
    assert is_public(address) is public


def send(url, answers, *, admin=False, also_allowed=()):
    seen = []

    def inner(request):
        seen.append(request)
        return httpx.Response(200)
    transport = PublicAddressTransport(httpx.MockTransport(inner), resolver=lambda host, port: answers[host],
                                       also_allowed=also_allowed)
    with scoped(user_scope("user", is_admin=admin)), httpx.Client(transport=transport) as client:
        client.post(url)
    return seen[0]


def test_users_reach_public_hosts_pinned_to_the_checked_address():
    request = send("https://model.example/v1/chat", {"model.example": ["93.184.216.34", "10.0.0.1"][:1]})
    assert request.url.host == "93.184.216.34" and request.headers["host"] == "model.example"
    assert request.extensions["sni_hostname"] == "model.example"


@pytest.mark.parametrize("url, answers", [
    ("http://localhost:8188/", {"localhost": ["127.0.0.1"]}),
    ("http://192.168.31.64/", {"192.168.31.64": ["192.168.31.64"]}),
    ("https://rebind.example/", {"rebind.example": ["93.184.216.34", "10.0.0.5"]}),
])
def test_users_cannot_reach_private_hosts(url, answers):
    with pytest.raises(ModelConfigurationError):
        send(url, answers)


def test_administrators_may_use_private_hosts():
    assert send("http://192.168.31.64:8000/v1", {}, admin=True).url.host == "192.168.31.64"


def test_extra_networks_count_as_public():
    networks = parse_networks("198.18.0.0/15, fd00::/8")
    assert send("https://model.example/", {"model.example": ["198.18.0.7"]}, also_allowed=networks).url.host == "198.18.0.7"
    with pytest.raises(ModelConfigurationError):
        send("https://model.example/", {"model.example": ["198.18.0.7", "10.0.0.1"]}, also_allowed=networks)
