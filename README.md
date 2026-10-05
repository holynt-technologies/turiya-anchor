# Turiya anchor

**Specification version 1, published 2026-09-30.**

What a receipt is, how to check one without us, and the public keys that say which receipts are
ours.

## Why this repository exists

Every Turiya receipt carries its signing key inside itself, in `key_cert`. That makes the chain
internally consistent: you can check that whoever holds that key signed that record. It does not
tell you the key is ours. On our own server, that claim is ours to make and yours to take on trust.

This repository is the out-of-band answer. It is public, it has a commit history, and it is not
editable by anyone quietly.

**Availability depends on one host.** This repository is readable at
`github.com/holynt-technologies/turiya-anchor`, and that is the only place it is readable. We keep a
private mirror so that losing that host costs a re-push rather than the record, but a mirror is not
a second public copy: nobody outside the company can read it. If the host becomes unreachable, the
claim this repository makes is unverifiable until we restore it somewhere else.

That is a deliberate trade rather than an oversight, and it is written here so a reader does not
assume two hosts where there is one.

## What is here

| path | what it is |
|---|---|
| `RECEIPT_SPEC.md` | The format. Normative for how to check a receipt. |
| `vectors/` | Test vectors. Four must pass. Two must fail. |
| `receipts/` | A copy of every published receipt, with `MANIFEST.json`. |
| `keys/` | The root public key, and the retirement list. |

## The keys, and how to check one is ours

`keys/root-public-key.pem` is the master public key. Every receipt carries it inside its
`key_cert`, so a receipt's chain is internally consistent on its own. What that cannot tell you is
whose key it is. This file is the statement that it is ours, in a repository whose history cannot
be quietly rewritten.

To check it against the record, pull the key out of any published receipt and compare:

```
python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['key_cert']['root_public_key'].strip())" <any receipt>
```

That must equal `keys/root-public-key.pem`, character for character. It does for every receipt here
that carries one.

**`keys/retirements.json` is the retirement list, and it is empty.** That is the honest statement
that no key has been retired, not a placeholder. It lives here rather than only on our server for
the reason the rest of this repository exists: a list nobody reads protects nobody, and this is the
copy that would have to change in public if a key were ever compromised.

Both are checked rather than promised. A check on our side fails if the published key stops
matching the one the receipts carry, or if this retirement list and the one our site serves stop
agreeing.

## The receipts are a copy, and why that needs a check

This repository holds a **copy** rather than a link. A link would put our server back in the trust
path, which is the thing this repository exists to remove.

A copy cannot be silently corrupted. Every receipt is content-addressed, so change one byte and the
file fails its own hash. What a copy can do is go **stale**: we publish a receipt, the copy is not
refreshed, and this repository quietly describes a smaller tree than exists.

So the copy carries a manifest, and we run a check that compares it against the tree we publish
from. It fails when the counts disagree, when the set digest moves, when a receipt is in one place
and not the other, or when a copied file differs from its source. The check runs here, not in this
repository, because it has to read both sides.

**The manifest's numbers are derived, not written down.** If you want to know how many receipts
there are, read `receipts/MANIFEST.json` rather than any prose, here or anywhere else. The derived
figure is the only one that cannot drift.

**What the manifest pins is the set, not the bytes.** The digest is taken over each receipt's path
and its content address. A receipt's file may legitimately be reformatted, because the hashed input
is canonicalised rather than read verbatim; what a receipt actually claims is its content address,
so that is what gets pinned.

## What this repository does not contain

The compiler, the archetype implementations, the calibration, the thresholds, and the decision
rules. Those decide *what* is tested and how hard. They are not needed to check a receipt and they
are not here.

## The licence, and the one thing it is for

Apache License 2.0. Two things about that choice.

The copyright grant is ordinary. The interesting half is the patent grant, which includes
**defensive termination**: if you take this specification and then sue someone over a patent you
claim it infringes, the grant you received ends.

The clause matters because a third party could hold something reading on this scheme, take the free
specification, and then litigate. We cannot prevent that. We can decline to keep helping.

We chose Apache 2.0 over a Creative Commons licence for exactly this reason. CC BY carries no patent
grant at all.

## How to check a receipt

1. Read `RECEIPT_SPEC.md`, section 3. Canonicalisation is the part that decides whether your
   implementation agrees with ours, and it is the part most often got wrong.
2. Build against `vectors/`. Reproduce `canonical.txt` byte for byte for each positive vector, and
   reject both `tampered-*`.
3. Check a real receipt from the published board.

If your implementation disagrees with ours on a vector, the vector is right and one of us is wrong.
Tell us which one you think it is.

## What checking a receipt proves

That the record has not changed since it was signed, and that the key named in it signed that
content address.

It does not prove the finding is correct. Not that the ground truth was right, not that the tests
were sufficient, not that the environment was representative. Cryptographic integrity is not
correctness, and an implementation that reports "verified" without keeping that distinction has done
the steps and missed the point.
