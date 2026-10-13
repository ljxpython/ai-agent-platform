"""Native TLS entrypoint: exactly one local manager, verified client certificates."""

import os
import ssl

import uvicorn
from uvicorn.protocols.http.h11_impl import H11Protocol

from runtime_service.sandbox_node.service import create_app
from runtime_service.workspace.target import secret_file


class MutualTLSProtocol(H11Protocol):
    def connection_made(self, transport):
        super().connection_made(transport)
        wrapped = self.app
        tls = transport.get_extra_info("ssl_object")
        certificate = tls.getpeercert() if tls else {}

        async def with_certificate(scope, receive, send):
            scope["sandbox_client_certificate"] = certificate
            return await wrapped(scope, receive, send)

        self.app = with_certificate


def main():
    if os.getenv("WEB_CONCURRENCY", "1") != "1":
        raise ValueError("Sandbox Node requires one manager process")
    uvicorn.run(
        create_app(),
        host=os.environ.get("SANDBOX_LISTEN_HOST", "0.0.0.0"),
        port=int(os.environ.get("SANDBOX_LISTEN_PORT", "19111")),
        workers=1,
        http=MutualTLSProtocol,
        ws="none",
        proxy_headers=False,
        ssl_certfile=str(secret_file("SANDBOX_TLS_CERT_FILE")),
        ssl_keyfile=str(secret_file("SANDBOX_TLS_KEY_FILE")),
        ssl_ca_certs=str(secret_file("SANDBOX_TLS_CLIENT_CA_FILE")),
        ssl_cert_reqs=ssl.CERT_REQUIRED,
        limit_concurrency=32,
        timeout_graceful_shutdown=80,
        access_log=False,
    )


if __name__ == "__main__":
    main()
