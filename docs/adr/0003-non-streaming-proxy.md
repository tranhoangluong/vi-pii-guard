# ADR-0003: Non-streaming OpenAI-compatible proxy first

- Status: accepted
- Date: 2026-11-23

## Context

Teams already call LLMs through the OpenAI chat-completions format. A drop-in proxy lets them
add redaction by changing only `base_url`. Restoring placeholders in a stream is harder: a
placeholder such as `[PERSON_1]` can be split across chunks.

## Decision

- Implement `POST /v1/chat/completions`. Redact string contents and `text` parts of every
  message, forward the request upstream, then restore `choices[].message.content`.
- Reject `stream=true` with a clear 400 error for now.
- Use the configured upstream key if set; otherwise forward the client's `Authorization` header.
- Pass upstream error responses through unchanged; return 502 when the upstream is unreachable.
- Log only counts and status codes, never message content.

## Consequences

- Clients that require streaming cannot use the proxy yet. Streaming support needs a small
  buffer that holds back text after an unmatched `[` until the placeholder closes.
- Tool-call arguments and non-text parts (images, audio) are not redacted yet.
