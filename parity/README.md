# Parity data

Evidence and judgment, kept in separate files, behind
[`scripts/parity.py`](../scripts/parity.py).

| File | What it is | Edited by |
| --- | --- | --- |
| `upstream.tsv` | Both upstream tools' command lists, with the URL, date and SHA-256 of the document each was read from | `--refresh` only, never by hand |
| `mapping.tsv` | Which upstream commands this CLI provides under another name (`alias`), and which it will not provide at all (`excluded`, with a reason) | by hand |
| `baseline.json` | The covered-command floor the ratchet enforces | `--update` |

```console
$ python3 scripts/parity.py                 # regenerate the README table
$ python3 scripts/parity.py --check         # CI gate: offline, read-only
$ python3 scripts/parity.py --missing gog   # what to build next
$ python3 scripts/parity.py --refresh       # re-read upstream (needs network)
```

An `excluded` row is removed from the denominator, so it never counts against
coverage — which is exactly why each one has to give a reason that can be
argued with, and why `tests/test_parity.py` refuses a bare one. An `alias`
row counts as covered only if the command it names still exists; a mapping
that outlives its target fails the gate rather than propping up the number.
