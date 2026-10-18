# Verify a receipt

`verify_receipt.py` checks a Turiya receipt without the product. It has no probe
schema, no generator, and no compiler import. It knows only the receipt envelope
defined in `RECEIPT_SPEC.md`.

```bash
pip install cryptography
python3 verify/verify_receipt.py receipts/<id>.json
```

It recomputes the content address and checks the Ed25519 signature against the
key in the receipt.

## What it proves

That the record has not been altered since signing, and that the key named in it
signed that content address.

## What it does not prove

That the finding is correct. A signature is not evidence of correctness.
