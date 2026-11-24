# data/

Generated files only. This folder is git-ignored except for this README.

- `synthetic/`: output of `scripts/generate_data.py` (fictional, structurally valid values).
- `gold/`: hand-labeled evaluation set. Write texts that *look* real but use invented values.

**Never put real personal data here**, even temporarily: no real names with real phone
numbers, no real ID numbers, no customer logs. Doing so would itself be a personal-data
processing activity under Vietnamese law.

JSONL format, one example per line:

```json
{"id": "cs01-000001", "text": "Tôi tên là Lê Văn Nam, SĐT 0912345678", "spans": [{"start": 11, "end": 21, "label": "PERSON"}, {"start": 27, "end": 37, "label": "PHONE"}], "meta": {"domain": "customer_support"}}
```

Offsets are character offsets into the NFC-normalized `text`.
