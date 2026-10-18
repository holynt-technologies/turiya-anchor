#!/usr/bin/env python3
"""Verify a Turiya receipt without the product.

This tool knows the receipt envelope and nothing about how a receipt was produced.
It has no probe schema, no generator, and no compiler import. It recomputes the
content address and checks the Ed25519 signature against the key in the receipt.

    python3 verify_receipt.py receipt.json [more.json ...]

Exit 0 when every receipt verifies, 1 otherwise.

A verified receipt proves the record is unchanged since signing and that the key
named in it signed it. It does not prove the finding is correct.
"""
from __future__ import annotations

import json
import sys

from cryptography.hazmat.primitives.serialization import load_pem_public_key


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def recompute_record_hash(record: dict) -> str:
    import hashlib
    body = {k: v for k, v in record.items() if k != "record_hash"}
    return hashlib.sha256(canonical(body)).hexdigest()


def verify_flat(receipt: dict) -> tuple[bool, str]:
    import hashlib
    try:
        payload = {"schema": receipt["schema"], "outcome": receipt["outcome"]}
        claimed = receipt["record_hash"]
        public_key = receipt["public_key_pem"]
        signature = bytes.fromhex(receipt["signature"])
    except (KeyError, TypeError, ValueError) as e:
        return False, f"malformed flat receipt: {e}"
    actual = hashlib.sha256(canonical(payload)).hexdigest()
    if claimed != actual:
        return False, "record_hash mismatch: the record has been altered"
    try:
        key = load_pem_public_key(public_key.encode())
        key.verify(signature, actual.encode("ascii"))
    except Exception as e:  # noqa: BLE001
        return False, f"signature invalid: {e}"
    return True, "valid"


def verify_certificate(receipt: dict) -> tuple[bool, str]:
    record = receipt.get("record")
    sig = receipt.get("signature") or {}
    if not isinstance(record, dict) or not isinstance(sig, dict):
        return False, "malformed certificate: missing record or signature"
    claimed = record.get("record_hash")
    actual = recompute_record_hash(record)
    if claimed != actual:
        return False, "record_hash mismatch: the record has been altered"
    if sig.get("signed_hash") != actual:
        return False, "signed_hash does not match the record content"
    if sig.get("algorithm") != "ed25519":
        return False, f"unsupported algorithm: {sig.get('algorithm')!r}"
    try:
        key = load_pem_public_key((sig.get("public_key") or "").encode())
        key.verify(bytes.fromhex(sig.get("signature", "")), actual.encode("ascii"))
    except Exception as e:  # noqa: BLE001
        return False, f"signature invalid: {e}"
    return True, "valid"


def verify(receipt: dict) -> tuple[bool, str]:
    if "certificate_version" in receipt:
        return verify_certificate(receipt)
    if "schema" in receipt and "outcome" in receipt:
        return verify_flat(receipt)
    return False, "unknown envelope: not a flat or certificate receipt"


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 1
    failed = 0
    for path in argv:
        try:
            with open(path, encoding="utf-8") as fh:
                receipt = json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            print(f"{path}: invalid: cannot read: {e}", file=sys.stderr)
            failed += 1
            continue
        ok, why = verify(receipt)
        print(f"{path}: {'valid' if ok else 'invalid: ' + why}")
        if not ok:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
