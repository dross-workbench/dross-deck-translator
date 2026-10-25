"""Generate local-only credentials/certificate. Never print the token to logs."""
import argparse
import ipaddress
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

p = argparse.ArgumentParser()
p.add_argument('--bind', default='127.0.0.1')
p.add_argument('--ollama', required=True)
p.add_argument('--models', required=True)
args = p.parse_args()
address = ipaddress.ip_address(args.bind)
if not (address.is_private or address.is_loopback) or address.is_unspecified:
    p.error('Bind to a specific private LAN IP or loopback address')
folder = Path(__file__).resolve().parent / '.local'
folder.mkdir(exist_ok=True)
config_path = folder / 'config.json'
config = json.loads(config_path.read_text()) if config_path.exists() else {'token': secrets.token_urlsafe(32)}
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Dross Translation Gateway')])
cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=5))
        .not_valid_after(datetime.now(timezone.utc)+timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(address)]), critical=False)
        .sign(key, hashes.SHA256()))
(folder/'server.key').write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
(folder/'server.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
config.update(bind=args.bind, port=18765, ollama=str(Path(args.ollama).resolve()), models=str(Path(args.models).resolve()),
              fingerprint=cert.fingerprint(hashes.SHA256()).hex())
config.setdefault('translation_model', 'translategemma:4b')
config.setdefault('analysis_model', 'qwen3:1.7b')
config_path.write_text(json.dumps(config, indent=2))
print('Local configuration created. Pairing details are in server/.local/config.json; keep this file private.')
