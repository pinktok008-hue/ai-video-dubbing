# IMPLEMENTATION_RULES.md

# AI Video Dubbing Platform V3.1 LTS

## Implementation Rules

Version: 1.0

Status: Mandatory

---

# IMPORTANT

These rules are mandatory.

Every future code modification must follow these rules.

No exception.

If an existing file violates these rules,
rewrite the entire file.

Never leave partial implementations.

---

# RULE 1

Never write temporary code.

Forbidden:

- TODO
- FIXME
- HACK
- placeholder
- dummy implementation
- fake implementation
- pass
- mock production logic

Every implementation must be production ready.

---

# RULE 2

Never return partial code.

Always rewrite the complete file.

Never return patches.

Never return snippets.

Never return diff.

Always provide the complete production file.

---

# RULE 3

Never break backward compatibility.

Old API must continue working.

Existing endpoints must continue working.

---

# RULE 4

Never remove existing features.

Only improve.

Only extend.

---

# RULE 5

Every new feature must be configurable.

Nothing should be hardcoded.

Everything must come from config.py.

---

# RULE 6

Every service must have one responsibility.

No God class.

No God file.

---

# RULE 7

Business logic must never exist inside FastAPI routes.

Routes should only:

- validate request
- call service
- return response

---

# RULE 8

Every feature must have proper logging.

Required log levels:

DEBUG

INFO

WARNING

ERROR

CRITICAL

No silent failures.

---

# RULE 9

Every exception must include useful context.

Bad:

Exception("Failed")

Good:

Exception(
"Edge TTS synthesis failed for task abc123 because websocket returned 403."
)

---

# RULE 10

Never swallow exceptions.

Always log them.

Always preserve traceback.

---

# RULE 11

All external processes must use timeout.

Examples

FFmpeg

FFprobe

Piper

Whisper

Everything.

---

# RULE 12

Every subprocess must return:

stdout

stderr

return code

timeout information

---

# RULE 13

Every engine must implement:

initialize()

generate()

health_check()

shutdown()

---

# RULE 14

Manager classes must never know implementation details.

They only orchestrate.

---

# RULE 15

Every engine must register itself.

Never hardcode engines.

Use registry pattern.

---

# RULE 16

Every feature must support future extension.

Open/Closed Principle.

---

# RULE 17

Never duplicate code.

Extract shared utilities.

---

# RULE 18

Never duplicate FFmpeg commands.

Create reusable builders.

---

# RULE 19

Never duplicate subtitle logic.

---

# RULE 20

Never duplicate translation logic.

---

# RULE 21

Every file must contain:

Module description

Python version

Purpose

---

# RULE 22

Every public function must have:

Args

Returns

Raises

---

# RULE 23

Use type hints everywhere.

No untyped public functions.

---

# RULE 24

No global mutable state.

---

# RULE 25

No blocking code inside async functions.

---

# RULE 26

CPU intensive work must run in background threads.

---

# RULE 27

Long tasks must support cancellation.

---

# RULE 28

Progress updates are mandatory.

---

# RULE 29

Every stage must report progress.

---

# RULE 30

Never lose task state.

Recover after restart whenever possible.

---

# RULE 31

Support resumable processing.

---

# RULE 32

Support future distributed workers.

---

# RULE 33

Support queue abstraction.

---

# RULE 34

Support future Redis.

---

# RULE 35

Support future PostgreSQL.

---

# RULE 36

Support future S3 storage.

---

# RULE 37

Support future object storage.

---

# RULE 38

Keep Render Free compatible.

---

# RULE 39

Optional dependencies must remain optional.

---

# RULE 40

Heavy AI models must never load unless enabled.

---

# RULE 41

Gracefully skip unavailable engines.

---

# RULE 42

Fallback chain must continue automatically.

---

# RULE 43

One engine failure must never fail entire request.

Unless every engine fails.

---

# RULE 44

Validate configuration during startup.

---

# RULE 45

Fail fast on invalid configuration.

---

# RULE 46

Never expose secrets.

---

# RULE 47

Never log API keys.

---

# RULE 48

Never log tokens.

---

# RULE 49

Sanitize filenames.

---

# RULE 50

Validate uploaded files.

---

# RULE 51

Limit upload size.

---

# RULE 52

Reject unsupported formats.

---

# RULE 53

Always preserve original video.

---

# RULE 54

Intermediate files must be isolated.

---

# RULE 55

Automatic cleanup.

---

# RULE 56

Never delete outputs.

---

# RULE 57

Retry transient failures.

---

# RULE 58

Never retry validation errors.

---

# RULE 59

Network retries use exponential backoff.

---

# RULE 60

Every retry must be logged.

---

# RULE 61

Pipeline must stop only on unrecoverable errors.

---

# RULE 62

Every stage must be independently testable.

---

# RULE 63

Every feature must have verification.

---

# RULE 64

No dead code.

---

# RULE 65

No unreachable code.

---

# RULE 66

No duplicate imports.

---

# RULE 67

No circular imports.

---

# RULE 68

No wildcard imports.

---

# RULE 69

No hidden side effects.

---

# RULE 70

Every new feature must include:

Architecture update

Documentation update

Migration update

Verification update

---

# FINAL RULE

Quality is more important than speed.

Never optimize by reducing correctness.

Always prefer production-grade implementation over quick implementation.
