"""Unit tests for CoAP client and discovery protocol."""

import asyncio
import json
import socket
from backend.coap_client import (
    CODE_CHANGED,
    CODE_CONTENT,
    METHOD_GET,
    METHOD_POST,
    OPT_URI_PATH,
    OPT_URI_QUERY,
    TYPE_ACK,
    TYPE_CON,
    TYPE_NON,
    CoapClient,
    CoapMessage,
    extract_device_info,
    parse_link_format,
)


def test_coap_message_encoding_decoding():
    msg = CoapMessage(
        mtype=TYPE_CON,
        code=METHOD_GET,
        message_id=0x1234,
        token=b"\xab\xcd",
        payload=b'{"hello":"world"}',
    )
    msg.add_uri_path(".well-known/core")
    msg.add_uri_query("since=10&limit=5")

    encoded = msg.encode()
    decoded = CoapMessage.decode(encoded)

    assert decoded.type == TYPE_CON
    assert decoded.code == METHOD_GET
    assert decoded.message_id == 0x1234
    assert decoded.token == b"\xab\xcd"
    assert decoded.payload == b'{"hello":"world"}'

    # Check parsed options
    paths = [v.decode("utf-8") for num, v in decoded.options if num == OPT_URI_PATH]
    queries = [v.decode("utf-8") for num, v in decoded.options if num == OPT_URI_QUERY]
    assert paths == [".well-known", "core"]
    assert queries == ["since=10", "limit=5"]
    print("CoAP message encode/decode test passed!")


def test_link_format_and_info_extraction():
    raw_core = (
        '</sensors>;rt="sensors",</logger>;rt="data-logger";if="logger",'
        '</log>;rt="data-sync";if="logger",</display>;rt="display";if="actuator";ep="pico-2w-01"'
    )
    res = parse_link_format(raw_core)
    assert len(res) == 4
    assert res[0]["href"] == "/sensors"
    assert res[1]["rt"] == "data-logger"

    info = extract_device_info(raw_core, "192.168.1.100")
    assert info["device_id"] == "pico-2w-01"
    assert "data-sync" in info["capabilities"]
    assert "display" in info["capabilities"]
    print("Link format parsing test passed!")


class MockCoapServer:
    """Mock UDP CoAP server for async unit tests."""

    def __init__(self, port: int):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", port))
        self.sock.setblocking(False)
        self.running = True

    async def run(self):
        loop = asyncio.get_running_loop()
        while self.running:
            try:
                data, addr = await loop.sock_recvfrom(self.sock, 4096)
                req = CoapMessage.decode(data)

                # Determine path
                paths = [v.decode("utf-8") for num, v in req.options if num == OPT_URI_PATH]
                path = "/".join(paths)

                resp = CoapMessage(
                    mtype=TYPE_ACK if req.type == TYPE_CON else TYPE_NON,
                    message_id=req.message_id,
                    token=req.token,
                )

                if path == ".well-known/core":
                    resp.code = CODE_CONTENT
                    resp.payload = b'</sensors>;rt="sensors",</log>;rt="data-sync";ep="mock-board-01"'
                elif path == "log":
                    resp.code = CODE_CONTENT
                    resp_json = {
                        "data": [
                            {"ts": "2026-09-23T12:00:00", "device_id": "mock-board-01", "temp": 21.5, "hum": 45.0}
                        ],
                        "next_cursor": "2026-09-23:1",
                    }
                    resp.payload = json.dumps(resp_json).encode("utf-8")
                elif path == "display":
                    resp.code = CODE_CHANGED
                    resp.payload = b""
                else:
                    resp.code = 132  # 4.04 Not Found

                await loop.sock_sendto(self.sock, resp.encode(), addr)
            except Exception:
                if not self.running:
                    break
                await asyncio.sleep(0.01)

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass


async def test_client_requests():
    test_port = 56839
    server = MockCoapServer(test_port)
    server_task = asyncio.create_task(server.run())

    try:
        client = CoapClient(port=test_port)

        # 1. Test GET /log
        log_res = await client.get_log("127.0.0.1", cursor=None, size=10, port=test_port)
        assert len(log_res["data"]) == 1
        assert log_res["next_cursor"] == "2026-09-23:1"
        assert log_res["data"][0]["temp"] == 21.5
        print("CoAP GET /log test passed!")

        # 2. Test POST /display
        disp_res = await client.post_display("127.0.0.1", "Hello Pico!", port=test_port)
        assert disp_res is True
        print("CoAP POST /display test passed!")

    finally:
        server.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


async def main():
    test_coap_message_encoding_decoding()
    test_link_format_and_info_extraction()
    await test_client_requests()
    print("All CoAP client tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
