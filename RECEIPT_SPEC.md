# The Turiya receipt format. Specification, version 1.

> Written 2026-09-30. Derived from the code that produces receipts and the code that checks them.
> Where this document and those implementations disagree, one of them is wrong. §11 records the two
> places they currently do not quite agree, which is a fact about the format rather than about
> anyone's repository.
>
> **Status.** Sections 3 to 6 and 8 are **normative**. Section 7 is descriptive. Section 11 is a
> list of known limits, not aspirations.
>
> **What this specification is for.** It lets anyone check a receipt without our code, our server,
> or our permission. It does **not** let anyone produce one. Producing a receipt means deciding
> what to test and how, which is the compiler, and the compiler is not in this document.

---

## 1. Terminology

| term | meaning |
|---|---|
| **record** | The verdict. A JSON object describing what was tested and what was found. |
| **receipt** | The record wrapped in its content address and a signature. This document's subject. |
| **envelope** | Which of the two shapes a receipt takes. There are two, and they are not interchangeable. |
| **canonical form** | The exact bytes a content address is computed over. Defined in §3. |
| **content address** | `record_hash`. Lowercase hex SHA-256 of the canonical form. |
| **key id** | A short label for a public key. Defined in §6. |

---

## 2. The two envelopes

### 2.1 Flat

Used by `sweverify/1` and `agentverify/1`.

```json
{
  "schema": "sweverify/1",
  "outcome": { },
  "record_hash": "<64 lowercase hex>",
  "signature": "<128 lowercase hex>",
  "key_id": "<16 lowercase hex>",
  "public_key_pem": "<SPKI PEM>"
}
```

The **hashed input** is the object `{"schema": ..., "outcome": ...}` and nothing else. Every other
field sits outside the content address, so `signature`, `key_id` and `public_key_pem` may be
reformatted without breaking it.

### 2.2 Certificate

Used everywhere else. `certificate_version` is `"1"`.

```json
{
  "certificate_version": "1",
  "record": { "...": "...", "record_hash": "<64 lowercase hex>" },
  "signature": {
    "algorithm": "ed25519",
    "key_id": "<16 lowercase hex>",
    "verifier_version": "<string>",
    "signed_hash": "<64 lowercase hex>",
    "signature": "<128 lowercase hex>",
    "public_key": "<SPKI PEM>"
  },
  "key_cert": { },
  "timestamp": { }
}
```

`key_cert` and `timestamp` are optional. The **hashed input** is `record` with its `record_hash`
member removed.

**`key_cert`** is the master key's note, present when an everyday key signed. It carries the master's
public key, and the chain is checked in §8 step 6. It is absent when the master signed directly,
which is how certificates issued before the seal still verify.

**`timestamp`** is an RFC 3161 token over the content address, obtained from an independent
timestamping authority. It is outside the content address. Verification of the token is a separate
procedure and is not required by §8.

---

## 3. Canonicalisation (normative)

The target is the byte sequence produced by Python's

```python
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
```

Every rule below exists because that is what the signer runs. An implementation that agrees with
Python on ordinary input and disagrees on edge cases is not conformant, it is lucky.

### 3.1 Both envelopes

- **No insignificant whitespace.** Separators are `,` and `:` with nothing around them.
- **Output is UTF-8.** Because `ensure_ascii=True`, the canonical form contains no byte above
  `0x7F`. Every non-ASCII character is escaped, so the canonical bytes are pure ASCII and the
  UTF-8 encoding of them is the same as their ASCII bytes.
- **Array order is preserved.** Nothing sorts arrays.
- **Object keys are sorted ascending.** The comparison is defined in §3.4 and it is the part most
  likely to be got wrong.
- **The hash is over the canonical bytes**, never over the file as written.

### 3.2 The flat envelope canonicalises *values*

Build the object `{"schema": <schema>, "outcome": <outcome>}` from the parsed JSON and serialise it
by these rules:

| input | output |
|---|---|
| `null` | `null` |
| `true` / `false` | `true` / `false` |
| integer | its decimal digits, with `-` if negative |
| string | escaped per §3.3, wrapped in `"` |
| array | `[` items joined by `,` `]` |
| object | `{` key/value pairs joined by `,` `}`, keys sorted per §3.4, each key escaped as a string |

**Constraint.** Numbers in a flat envelope's hashed input must be **integers**. See §11.1.

### 3.3 String escaping

Applied to every string, both keys and values.

| character | output |
|---|---|
| `"` | `\"` |
| `\` | `\\` |
| newline | `\n` |
| carriage return | `\r` |
| tab | `\t` |
| backspace | `\b` |
| form feed | `\f` |
| code point below `0x20`, other than the five above | `\u` then four **lowercase** hex digits |
| code point from `0x20` to `0x7E` | the character itself |
| code point `0x7F` and above, up to `0xFFFF` | `\u` then four **lowercase** hex digits |
| code point above `0xFFFF` | **two** `\u` escapes: the high surrogate, then the low surrogate, each four lowercase hex digits |

`0x7F` (delete) is escaped. `0x2F` (slash) is not. Hex digits are lowercase, always four, zero-padded.

### 3.4 Key ordering, and the astral problem

Sort keys **ascending by Python string comparison**, which is by Unicode code point.

> **This is the one rule where the current implementations diverge from the specification.**
> JavaScript's `<` on strings compares UTF-16 code units. For every character in the Basic
> Multilingual Plane the two orders agree, which is why this has never mattered: **no key or value
> in any published receipt contains a character above `0xFFFF`** (checked over all 57 on
> 2026-09-30). They disagree above it. Measured:
>
> ```
> keys  ["a", "\u{10000}", "｡"]
> Python (code point)  ->  a, ｡, 𐀀
> JavaScript (UTF-16)  ->  a, 𐀀, ｡
> ```
>
> **Constraint:** a conformant signer must not place a character above `0xFFFF` in an object key.
> A verifier that sorts by UTF-16 code unit is conformant for every receipt that satisfies that
> constraint and non-conformant for any that does not.

### 3.5 The certificate envelope canonicalises *raw text*

This is the important difference from §3.2, and it is deliberate.

An implementation must canonicalise the **raw serialised bytes of `record`**, not re-serialise the
parsed value. Two reasons, and the second is the one that bites:

1. Re-serialising loses the original token spelling.
2. **JavaScript cannot round-trip Python's floating-point rendering.** Python writes `1.0` for the
   float `1.0`; JavaScript's `String(1.0)` is `"1"`. A re-serialising verifier would compute a
   different content address and report a valid receipt as tampered with.

So, from the raw text:

- Locate the top-level member whose key is `record`.
- Sort its members ascending by their **quoted key text**, per §3.4.
- Strip whitespace **only between tokens**. Never inside a string.
- **Preserve every number token exactly as written**, including `1.0`, `1e-05`, `-0.0` and any
  trailing zero. Do not parse and re-render numbers.
- **Omit the member whose key is `record_hash`.** That member is the output, so it cannot be an
  input.
- Emit `{k:v,...}` with no whitespace.

A member of `record` whose value is a nested object or array is canonicalised by the same rules,
recursively.

---

## 4. Content address

```
record_hash = lowercase_hex( SHA-256( canonical_bytes ) )
```

64 hex characters, lowercase. This is the only content address in the format. The flat envelope
stores it once, at `record_hash`. The certificate envelope stores it twice: at `record.record_hash`
and again at `signature.signed_hash`. **Both must equal the recomputed value**, and §8 fails if they
disagree with each other even when one of them matches.

An Ed25519 signature is **not** taken over the canonical bytes. See §5.

---

## 5. Signature

```
signature = Ed25519_sign( private_key, ASCII_bytes( record_hash ) )
```

The signed message is the **content address as a 64-character ASCII string**, not the 32 raw bytes
of the digest. This is worth stating twice because it is the most common way an independent
implementation gets a receipt wrong while believing it is right: the signature verifies over the
hex text.

- Algorithm: **Ed25519**, PureEdDSA, no pre-hash.
- Key encoding for signing: PKCS#8 PEM, unencrypted.
- Key encoding in the receipt: **SubjectPublicKeyInfo PEM**.
- Signature encoding in the receipt: **lowercase hex**, 128 characters.
- `signature.algorithm` is the string `"ed25519"`. A verifier must reject any other value.

---

## 6. Key identity

```
key_id = lowercase_hex( SHA-256( public_key_pem ) )[:16]
```

The digest is taken over the **PEM text as it appears in the receipt**, so the same key with a
different PEM line-wrapping yields a different `key_id`. The first 16 hex characters are kept.

`key_id` is a label, not a security control. A verifier must check the signature against the key,
not trust the label.

---

## 7. The verdict lattice (descriptive)

`outcome.verdict` is one of four values. Their semantics are not part of the content address and are
recorded here so a reader knows what a receipt asserts.

| verdict | meaning |
|---|---|
| `falsified` | The claimed effect was re-run and did not hold. |
| `not_falsified` | We tried to break the claim and could not, within a defined set of attacks. |
| `certified` | A checkable property held, and the proof is available. |
| `indeterminate` | There was nothing checkable to test. |

There is no verdict of `true`, and its absence is a design decision rather than an omission.

---

## 8. Verification procedure (normative)

Given a receipt, an implementation must do the following in order. Each step's failure is named
because the reason matters to whoever is checking.

**Flat envelope**

1. Parse the file as JSON. If it does not parse, fail.
2. Canonicalise `{"schema": ..., "outcome": ...}` per §3.2.
3. Compute SHA-256 over those bytes. If the result is not `record_hash`, fail: the record was
   altered after signing.
4. Decode `public_key_pem` per §5. If it will not decode, fail.
5. Verify the Ed25519 signature over `ASCII_bytes(record_hash)` using the hex-decoded `signature`
   and that key. If it does not verify, fail.

**Certificate envelope**

1. Parse the file as JSON. If it does not parse, fail.
2. Canonicalise the raw text of `record` per §3.5. If `record` is missing, fail.
3. Compute SHA-256 over those bytes. If the result is not `record.record_hash`, fail.
4. If `signature.signed_hash` is not equal to that result, fail.
5. Decode `signature.public_key` per §5. If it will not decode, fail.
6. Verify the Ed25519 signature over `ASCII_bytes(signed_hash)` using the hex-decoded
   `signature.signature` and that key. If it does not verify, fail.
7. If `key_cert` is present, verify that the everyday key in `signature.public_key` is certified by
   the master key in `key_cert`, and that the master key is not retired.

Steps 4 and 6 are separate. A receipt whose `signed_hash` disagrees with its record, or whose
signature was made over a different hash, must fail even if the other check passes.

---

## 9. Test vectors

Each vector is a receipt that exists in the published tree, with the canonical bytes and the content
address recorded beside it, so an implementation can be diffed against ours rather than argued with.

| vector | envelope | what it exercises | must |
|---|---|---|---|
| `flat-sweverify` | flat, `sweverify/1` | the value-based canonicaliser | pass |
| `flat-agentverify` | flat, `agentverify/1` | a second flat schema | pass |
| `certificate-with-keycert` | certificate | the raw-text canonicaliser, with the master's note present | pass |
| `certificate-escapes` | certificate | non-ASCII and control characters surviving `ensure_ascii` | pass |
| `tampered-flat` | flat | one character changed inside `outcome` | **fail** |
| `tampered-certificate` | certificate | one character changed inside `record` | **fail** |

Each positive directory holds `receipt.json` (the input), `canonical.txt` (the exact bytes hashed,
**without** a trailing newline), and `expected.json` (the content address, the signed message, the
signature, and the public key). A conformant implementation reproduces `canonical.txt` byte for byte
and `record_hash` exactly.

**The two negative vectors are the ones that test anything.** An implementation that returns
"valid" unconditionally passes every positive vector here. `tampered-*` carry a single changed
character in the hashed region and **must be rejected**. Their `expected.json` says so, and the
generator refuses to emit one unless it has first confirmed the tampered receipt no longer
reproduces its own claimed hash.

**Two notes on how these were chosen, since both were measured rather than assumed.**

There is no "plain certificate" vector, because there is no plain certificate: **every certificate
envelope in the published tree carries at least one escaped character** (38 of the 57, the rest
being flat; `counts-exempt`, same envelope axis as §11.1), so the escaping path is the ordinary one
rather than an exotic case.

And the vectors are generated, not hand-written, by reimplementing both canonicalisers
independently, and keeping a vector **only if the reimplementation's output hashes to the
`record_hash` the receipt already carries**. An independent reimplementation is a second opinion on
the format: where the two disagree, one of them is wrong. A vector that exists has therefore been
proved against a signed artefact rather than against its author's reading of the format.

---

## 10. What this specification does not define

- **How a claim becomes a test.** The compiler. Withheld.
- **What is tested and how hard.** The axes, the thresholds, the resampling protocol, the decision
  rules. Withheld.
- **The meaning or correctness of a verdict.** This specification defines what a receipt *is*, not
  whether it is *right*. See §12.
- **The timestamping authority protocol.** RFC 3161, elsewhere.

---

## 11. Known limits

### 11.1 The flat envelope cannot carry a float

§3.2 renders numbers the way the host language does. Python writes `1.0` for the float `1.0` and
JavaScript writes `1`. Where the two disagree, a flat receipt signed by one and checked by the
other fails its own content address while being perfectly valid.

Measured 2026-09-30, across the **57** in the published tree: **19 are flat envelopes, and none of
them carries a non-integer number in its hashed input**, so the divergence is latent rather than
live. `counts-exempt`: that partition (19 flat + 38 certificate) is by envelope across the whole
tree, which is a different axis from the per-directory count and from the canonical flat/wrapped
figures for the current set. The certificate envelope does not have this problem, because §3.5
preserves the token.

The fix, when it is needed, is to move flat receipts to a raw-text canonicaliser or to forbid
non-integer numbers at signing. Until then the constraint is a rule, not a hope.

### 11.2 The astral key-ordering divergence

See §3.4. The specification requires code-point ordering. Both current verifiers sort by UTF-16
code unit. They are conformant for every receipt that exists and non-conformant in principle.

### 11.3 Two canonicalisers is one more than it should be

A flat receipt and a certificate receipt with identical content canonicalise differently, because
one sorts parsed values and the other sorts raw tokens. That is a real inconsistency in the format
and it is recorded here rather than tidied away in prose.

---

## 12. What a verified receipt proves

A receipt that passes §8 proves that the record has not been altered since signing, and that the
key named in it signed that content address.

**It does not prove that the finding is correct.** Not that the ground truth was right, not that the
tests were sufficient, not that the environment was representative, not that something important
was left out.

Cryptographic integrity is not correctness. An implementation that reports "verified" without
distinguishing the two has implemented this specification's steps and missed its point.
