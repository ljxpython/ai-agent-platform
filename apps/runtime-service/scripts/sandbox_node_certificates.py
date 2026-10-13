"""Generate an isolated Node trust domain; never overwrite an existing private key."""

import argparse
import hashlib
import ipaddress
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def generate(directory, server_name, execution_host, allowed_ip, ca_source=None):
    directory = Path(directory).absolute()
    if any(path.is_symlink() for path in (directory, *directory.parents)):
        raise ValueError("certificate directory must not use symlinks")
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("output must be a new empty certificate directory")
    network = ipaddress.ip_network(allowed_ip)
    if network.prefixlen == 0:
        raise ValueError("caller IP must be restricted")
    import re

    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", execution_host):
        raise ValueError("invalid execution host")
    if (
        not server_name
        or len(server_name) > 253
        or any(c.isspace() for c in server_name)
    ):
        raise ValueError("invalid server name")
    now = datetime.now(UTC)
    if ca_source:
        source = Path(ca_source).absolute()
        paths = [source / "ca.pem", source / "ca-key.pem"]
        if any(p.is_symlink() for path in paths for p in (path, *path.parents)) or any(
            path.stat().st_mode & 0o077 for path in paths
        ):
            raise ValueError("CA source must use private files without symlinks")
        ca_key = serialization.load_pem_private_key(
            paths[1].read_bytes(), password=None
        )
        ca = x509.load_pem_x509_certificate(paths[0].read_bytes())
        if (
            ca.public_key().public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            != ca_key.public_key().public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            or not ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
            or ca.not_valid_after_utc < now + timedelta(days=90)
        ):
            raise ValueError(
                "CA does not match its key or cannot issue 90-day certificates"
            )
        ca_name = ca.subject
    else:
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        ca_name = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, "Runtime Sandbox CA")]
        )
        ca = (
            x509.CertificateBuilder()
            .subject_name(ca_name)
            .issuer_name(ca_name)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=730))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
                critical=False,
            )
            .add_extension(
                x509.KeyUsage(
                    True, False, False, False, False, True, True, False, False
                ),
                critical=True,
            )
            .sign(ca_key, hashes.SHA256())
        )
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    def save(name, data):
        descriptor = os.open(
            directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)

    def key_bytes(key):
        return key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )

    if ca_source is None:
        save("ca-key.pem", key_bytes(ca_key))
    save("ca.pem", ca.public_bytes(serialization.Encoding.PEM))
    for role, name, usage in (
        ("server", server_name, ExtendedKeyUsageOID.SERVER_AUTH),
        ("client", execution_host, ExtendedKeyUsageOID.CLIENT_AUTH),
    ):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        builder = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
            .issuer_name(ca_name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=90))
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None), critical=True
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                critical=False,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                critical=False,
            )
            .add_extension(x509.ExtendedKeyUsage([usage]), critical=False)
        )
        if role == "server":
            try:
                san = x509.IPAddress(ipaddress.ip_address(name))
            except ValueError:
                san = x509.DNSName(name)
            builder = builder.add_extension(
                x509.SubjectAlternativeName([san]), critical=False
            )
        certificate = builder.sign(ca_key, hashes.SHA256())
        save(role + "-key.pem", key_bytes(key))
        save(role + ".pem", certificate.public_bytes(serialization.Encoding.PEM))
    token = secrets.token_urlsafe(48)
    save("caller-token", token.encode())
    save(
        "callers.json",
        json.dumps(
            {
                execution_host: {
                    "certificate_cn": execution_host,
                    "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                    "allowed_ips": [str(network)],
                }
            },
            indent=2,
        ).encode(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--server-name", required=True)
    parser.add_argument("--execution-host", required=True)
    parser.add_argument("--allowed-ip", required=True)
    parser.add_argument(
        "--ca-source",
        type=Path,
        help="Existing offline CA directory for leaf/token rotation",
    )
    args = parser.parse_args()
    generate(
        args.output,
        args.server_name,
        args.execution_host,
        args.allowed_ip,
        args.ca_source,
    )
    print(
        "Node trust material created; certificates expire in 90 days. No secret values printed."
    )
