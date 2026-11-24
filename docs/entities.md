# Entity taxonomy

Offsets always refer to the NFC-normalized text. Scores are in `[0, 1]`; the default
threshold is `0.5`. Context keywords are matched case- and diacritic-insensitively within
40 characters before and 15 characters after a candidate.

| Type | Format | Validation | Context | Notes |
|---|---|---|---|---|
| `PERSON` | 1-4 capitalized syllables | none | trigger phrases: "tên là", "họ tên", "chủ tài khoản", kinship terms ("anh", "chị") | Rule baseline only. Lowercase names and names without a trigger need the NER model. |
| `ADDRESS` | street, ward/commune, (district), province | must contain an admin keyword | triggers: "địa chỉ", "giao đến", "thường trú" | Accepts both the pre-2025 three-level format and the post-2025 two-level format (districts removed on 1 July 2025). |
| `PHONE` | `0` + 9 digits, `+84`/`84` prefix, spaces or dots | carrier prefix (032-039, 09x, ...) | "sđt", "điện thoại", "zalo", "liên hệ" | Landlines: 11 digits starting with `02`. Penalized after "MST" or "STK". |
| `EMAIL` | RFC-like local@domain.tld | none | none | |
| `NATIONAL_ID` | 12 digits (CCCD / số định danh) or 9 digits (old CMND) | 12-digit: province code 001-096, birth year from the century/gender digit not in the future | "cccd", "căn cước", "cmnd", "định danh" | 9-digit values require context. Since 1 July 2025 the personal tax code of a citizen is the 12-digit ID, so it is labeled `NATIONAL_ID`. |
| `PASSPORT` | 1 letter + 7 digits | none | "hộ chiếu", "passport" | Requires context to pass the threshold. |
| `TAX_CODE` | 10 digits, or 10 digits + `-` + 3 digits | weights 31, 29, 23, 19, 17, 13, 7, 5, 3; check digit = 10 - (sum mod 11) | "mst", "mã số thuế" | A valid 10-digit phone may also pass the checksum: context decides. |
| `BANK_ACCOUNT` | 6-19 digits | none | required: "stk", "tài khoản", bank names | Account numbers have no public checksum, so context is mandatory. |
| `CARD_NUMBER` | 13-19 digits, optional spaces/dashes | Luhn, not all-identical digits | "thẻ", "visa", "napas" | |
| `LICENSE_PLATE` | `51F-123.45`, `51LD-123.45`, `59-X1 123.45`, older 4-digit forms | province prefix 11-99 | "biển số", "bks", "xe" | |
| `DATE_OF_BIRTH` | `dd/mm/yyyy`, `d-m-yyyy`, `ngày d tháng m năm yyyy` | real calendar date, not in the future | required: "sinh", "ngày sinh", "dob" | Other dates (appointments, deadlines) are not PII. |

## Hard negatives

The synthetic generator deliberately includes values that must **not** be redacted: order ids
(`2026…`, `DH…`), prices (`1.250.000đ`), hotlines (`1900 xxxx`), product and promo codes,
appointment dates and city names in general questions.
