# AI Video Dubbing Platform — V3.1 LTS Migration Report
### Multi-Engine TTS Architecture

**Date:** 2026-07-13
**Scope:** `backend_v3/` only. `frontend/` was inspected and found to already be
disconnected from this backend (it calls a different, older API shape —
`/dub-video`, `/status/{job_id}` — that `backend_v3` has never exposed), so it
was left untouched as out of scope.

---

## 1. What this migration actually was

Before writing any code, the full project was read file-by-file. Two findings
changed the plan from what the migration brief assumed:

1. **The live TTS implementation was already Edge TTS, not gTTS.**
   `requirements.txt` had no `gTTS` entry, and `services/tts_service.py`
   called `edge_tts.Communicate` directly and exclusively. There was no gTTS
   code anywhere to "replace."
2. **A multi-engine scaffold already existed but was incomplete and inert.**
   `services/tts/base.py` (a clean `BaseTTSEngine` ABC) and
   `services/tts/engines/__init__.py` (a registry) were present. The registry
   imported six engine modules — `gtts_engine.py`, `edge_engine.py`,
   `azure_engine.py`, `piper_engine.py`, `xtts_engine.py`,
   `elevenlabs_engine.py` — **none of which existed on disk.** Nothing in the
   app imported this package yet, so it was dead code, not a live bug.

The work was therefore: **finish the scaffold exactly as it was already
shaped**, wire it into the existing `TTSService` / `pipeline` / API with
additive-only changes. The engine finished first as default was Edge (to
match live V3.0 behavior at the time); it was then deliberately switched to
**gTTS as the production default**, per an explicit follow-up requirement,
with Edge, Azure, Piper, XTTS, and ElevenLabs all repositioned as optional,
explicitly-selectable engines, and the single-fallback mechanism generalized
into a configurable ordered fallback chain. See the revision note in §4.

---

## 2. Updated Project Tree

```
backend_v3/
├── .dockerignore
├── .env.example                          [MODIFIED] +multi-engine TTS vars
├── Dockerfile                             [MODIFIED] +optional-deps comment block
├── TEST_REPORT.md                         (unchanged — V3.0 historical record)
├── MIGRATION_V3.1.md                      [NEW] this document
├── app.py                                 [MODIFIED] +GET /tts/engines, engine validation
├── config.py                              [MODIFIED] +multi-engine TTS settings block
├── requirements.txt                       [MODIFIED] +gTTS, +azure-cognitiveservices-speech
├── requirements-optional.txt              [NEW] Piper + XTTS (not Render-Free-safe)
├── core/
│   ├── __init__.py
│   ├── file_manager.py                    [MODIFIED] extension-aware segment paths
│   ├── logger.py
│   ├── progress_manager.py
│   ├── task_manager.py
│   └── utils.py                           [MODIFIED] run_command() gained optional stdin
├── models/
│   ├── __init__.py
│   ├── response.py                        [MODIFIED] +tts_engine, +TTSEngineInfo/TTSEnginesResponse
│   └── task.py                            [MODIFIED] +tts_engine field
├── services/
│   ├── __init__.py
│   ├── audio_cleaner.py
│   ├── audio_extractor.py
│   ├── pipeline.py                        [MODIFIED] passes engine+language to TTS
│   ├── subtitle_service.py
│   ├── transcription_service.py
│   ├── translation_service.py
│   ├── tts_service.py                     [REWRITTEN] thin facade over TTSEngineManager
│   ├── video_merger.py
│   └── tts/
│       ├── __init__.py                    [NEW] missing package marker (see §6)
│       ├── base.py                        [MODIFIED] structured exceptions + real hooks
│       ├── cache.py                       [NEW] optional caching hook (no-op default)
│       ├── exceptions.py                  [NEW] structured exception hierarchy
│       ├── manager.py                     [NEW] engine resolution + automatic fallback
│       └── engines/
│           ├── __init__.py                (unchanged — already correct, see §6)
│           ├── azure_engine.py            [NEW]
│           ├── edge_engine.py             [NEW] — behavior-identical port of the old logic
│           ├── elevenlabs_engine.py       [NEW]
│           ├── gtts_engine.py             [NEW]
│           ├── piper_engine.py            [NEW]
│           └── xtts_engine.py             [NEW]
```

12 files modified, 11 files newly created (6 engines + 4 `services/tts/`
support modules + `requirements-optional.txt`), 0 files deleted, 0 files
renamed. `frontend/`, `TEST_REPORT.md`, and every other file not listed above
is byte-for-byte unchanged.

---

## 3. Requirements Changes

**`requirements.txt`** (installed in every deployment, including Render Free):
```diff
+ gTTS==2.5.4
+ azure-cognitiveservices-speech==1.42.0
```
ElevenLabs needed **no new dependency** — it's called directly via `httpx`,
which was already pinned for the Groq/edge-tts stack.

**`requirements-optional.txt`** (new file, NOT installed by default):
```
piper-tts==1.2.0
TTS==0.22.0          # Coqui, for XTTS v2 — pulls in PyTorch
```
Piper and XTTS pull in native/ML dependencies (onnxruntime, PyTorch) that are
incompatible with Render's free 512MB tier and meaningfully increase image
size and cold-start time. They are wired into the same plug-in interface as
every other engine, but their engine files use **lazy, function-scoped
imports** — `import gtts` / `import azure.cognitiveservices.speech` / `from
TTS.api import TTS` all happen inside `initialize()`/`generate()`, never at
module load time — so the app boots and every other engine works fine
whether or not these optional packages are installed. `GET /tts/engines`
simply reports them `available: false` until they are.

> **Caveat, stated plainly:** this sandbox has no network access, so none of
> these version pins could be checked against live PyPI. Run
> `pip install -r requirements.txt` (and `-r requirements-optional.txt` if
> using Piper/XTTS) in CI or locally before first deploy, and re-pin if a
> version has moved on. This is the same limitation `TEST_REPORT.md`
> documented for the original V3.0 build.

---

## 4. Environment Variable Changes

All new variables are optional with safe defaults — an operator who changes
nothing gets exactly the pre-migration behavior (Edge TTS only).

| Variable | Default | Notes |
|---|---|---|
| `DEFAULT_TTS_ENGINE` | `gtts` | Zero-config production default; needs no API key/binary/model |
| `FALLBACK_TTS_ENGINES` | `edge,azure,piper,xtts,elevenlabs` | Comma-separated ORDERED chain, tried left to right, skipping any unavailable engine, until one succeeds |
| `GTTS_DEFAULT_TLD`, `GTTS_SLOW` | `com`, `false` | |
| `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | `""` | Engine reports unavailable, not an error, until set |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_DEFAULT_VOICE_ID`, `ELEVENLABS_MODEL_ID` | `""`, `""`, `eleven_multilingual_v2` | |
| `PIPER_BINARY_PATH`, `PIPER_MODEL_DIR`, `PIPER_VOICE_MODEL_MAP` | `piper`, `storage/tts_models/piper`, `{}` | Map is a JSON object: `{"en":"en_US-lessac-medium.onnx"}` |
| `XTTS_MODEL_NAME`, `XTTS_DEVICE`, `XTTS_DEFAULT_SPEAKER_WAV` | Coqui XTTS v2 model id, `cpu`, `""` | Needs a reference speaker `.wav` |

> **Revision note:** an earlier draft of this document had `edge` as the
> default engine with a single `gtts` fallback, matching what the live V3.0
> code actually did at the time this migration began. That was deliberately
> changed after an explicit, direct requirement: gTTS is now the production
> default, Edge is optional, and the fallback mechanism was generalized from
> one engine to a configurable ORDERED CHAIN of engines (not just a rename).
> This is a real behavior change for any caller that omits `tts_engine` --
> stated plainly, not glossed over: those callers now get gTTS-quality audio
> instead of Edge's neural voices, unless they explicitly pass
> `"tts_engine": "edge"` or the operator reconfigures `DEFAULT_TTS_ENGINE`.

Full details with inline comments are in `.env.example`.

---

## 5. New API Surface (additive only)

- **`POST /dub`** gained an optional `tts_engine` field on the request body.
  Omitting it now resolves to `DEFAULT_TTS_ENGINE` (gTTS) -- see the revision
  note in §4 for why this is *not* behavior-identical to pre-migration
  requests, unlike everything else in this section.
- **`GET /tts/engines`** *(new endpoint)* — returns every registered engine's
  live availability and capability flags (voice selection, voice cloning,
  streaming, multi-speaker), which engine is currently the default, and each
  engine's rank (if any) in the configured ordered fallback chain.
- **`GET /status/{task_id}`** now also echoes back which `tts_engine` a task
  requested.

No existing endpoint, path, method, or response field was removed or
renamed. `DubRequest` and `StatusResponse` both use
`model_config = ConfigDict(extra="forbid")`, and adding new *optional*
fields to a `forbid`-mode model is additive by construction — it does not
change how any existing, unmodified client request is accepted or rejected.

One existing-behavior nuance worth flagging explicitly: the pre-existing
voice/language validation in `/dub` (`Settings.is_voice_valid_for_language`)
checks against the Edge-specific voice table. It has been scoped to only run
when the resolved engine is `"edge"` — otherwise it would have incorrectly
rejected valid Azure/ElevenLabs voice names that don't appear in Edge's
table. Behavior for Edge requests (the default, and 100% of pre-migration
traffic) is unchanged.

---

## 6. Notable engineering decisions

- **`services/tts/__init__.py` was missing** (a namespace-package gap) even
  though `services/tts/engines/__init__.py` — one level deeper — already had
  one, and every sibling package (`core/`, `models/`, `services/`) does too.
  Added for consistency; Python 3's implicit namespace packages would likely
  have tolerated the gap, but there was no reason to rely on that.
- **`services/tts/engines/__init__.py` required zero changes.** Its registry
  already imported exactly the six engine files by exactly the class names
  this migration implemented (`GTTSEngine`, `EdgeTTSEngine`,
  `AzureTTSEngine`, `PiperTTSEngine`, `XTTSEngine`, `ElevenLabsTTSEngine`).
  That's strong independent confirmation the original scaffold's design
  intent was read correctly.
- **Default engine is `gtts`; fallback is a configurable ORDERED CHAIN, not a
  single engine.** `FALLBACK_TTS_ENGINES` is a comma-separated list (default
  `edge,azure,piper,xtts,elevenlabs`) walked in order, skipping each
  unavailable/unconfigured engine automatically, until one succeeds or the
  chain is exhausted. The manager deduplicates the primary engine out of its
  own fallback chain (so if a caller explicitly requests `"azure"` and
  `FALLBACK_TTS_ENGINES` also contains `"azure"`, it isn't retried against
  itself).
- **A validation error short-circuits fallback.** This was caught during
  runtime testing (§7), not by inspection: an empty-text request was
  retrying against the fallback engine too, producing a confusing
  compound error for what is really just one bad request. Fixed in
  `manager.py` — a `TTSValidationError` now propagates immediately.
- **`clone_voice()` and `synthesize_stream()` are real hooks, not
  decoration.** They're defined on `BaseTTSEngine` with an honest
  `NotImplementedError` default. ElevenLabs and XTTS override `clone_voice()`
  with a genuine working implementation (both providers actually support
  cloning); Edge overrides `synthesize_stream()` with a genuine working
  implementation (`edge_tts.Communicate.stream()` is a real streaming API).
  Engines that don't support a capability inherit the honest default instead
  of a fabricated implementation.
- **Lip sync was deliberately not stubbed.** It's a computer-vision problem
  (face/mouth tracking against video frames), not a TTS-engine concern, and
  nothing in this codebase touches video frames today. Inventing a fake
  `services/lipsync_service.py` would have been scaffolding with no grounding
  in the real codebase — see §10 instead.

---

## 7. Verification Report

This sandbox has **no network access** (`pip install` cannot reach PyPI), so
verification used the same constraint-adapted methodology `TEST_REPORT.md`
already established for V3.0: lightweight behavioral stubs standing in for
third-party packages, real code exercised against them.

| Check | Method | Result |
|---|---|---|
| Syntax validity | `python3 -m py_compile` on all 32 `.py` files | **32/32 pass** |
| Full import graph | Behavioral stubs for `fastapi`, `pydantic`, `pydantic-settings`, `edge-tts`, `httpx`, `aiofiles`, `groq`, `deep-translator` on `PYTHONPATH`; imported all 29 modules in dependency order, `config` → engines → `services.tts_service` → `pipeline` → `app` | **29/29 import cleanly** |
| Runtime control flow | Real `TTSEngineManager` + `TTSRequest` objects, stubbed `edge_tts` | **13/13 behavioral assertions pass** (see below) |
| FastAPI route table | Constructed the real `app.py` module; enumerated `app.routes` | **10 routes**: the original 9 unchanged + `/tts/engines` added |
| Model backward compatibility | Constructed `DubRequest` with and without `tts_engine`; confirmed `extra="forbid"` still rejects unknown fields | **pass** |
| Dead code / placeholders | `grep` for `TODO`/`FIXME`/`XXX` and bare `pass` bodies across `services/tts/` | **none found** |

Runtime behavioral assertions (13/13 passed):
1. Default engine at the time of this test run (`edge`; later changed to
   `gtts` -- see §12) synthesized successfully via the stub.
2. Output file is written and non-empty.
3. `response.engine` correctly reports `"edge"`.
4. Explicit `engine_name="edge"` selection works.
5. An unconfigured `azure` request fails cleanly *and* correctly attempts
   the `gtts` fallback (which also correctly reports itself unavailable,
   since neither package is installed in this sandbox) — raising one clear
   `AllTTSEnginesFailedError` naming both failures, not a crash or a hang.
6. Empty-text input raises `TTSValidationError` immediately, without a
   wasted fallback attempt (the bug found and fixed in §6).
7. An unknown engine name (`"not_a_real_engine"`) is reported as a clean,
   catchable failure — not an unhandled `KeyError`/`ValueError`.
8. `list_engines()` enumerates all six registered engines by name.
9. `edge` reports `available=True`, `supports_streaming=True`.
10. `azure` (no key configured) reports `available=False`.
11. `elevenlabs` reports `supports_voice_cloning=True`.
12. `xtts` reports `supports_voice_cloning=True`.
13. (Combined with #5) fallback-failure error text names both engines.

**What could not be verified in this sandbox**, stated plainly rather than
glossed over:
- No live call was made to Edge, Azure, ElevenLabs, Piper, or XTTS —
  network access is disabled here. The stub for `edge_tts.Communicate`
  intentionally reproduces its real single-use-stream constraint (a second
  `.save()` call raises), because `edge_engine.py`'s retry logic is
  specifically written around that constraint — but it cannot confirm
  Microsoft's actual endpoint still behaves identically.
- `gTTS`, `azure-cognitiveservices-speech`, and `TTS` (Coqui) were **not**
  installed or stubbed, by design — their engine files use lazy imports
  specifically so this is safe, and the import-graph test (row 2 above)
  confirms the app boots correctly with them absent.
- Piper's actual subprocess invocation (binary + `.onnx` model) was not
  exercised — there is no Piper binary in this sandbox.

---

## 8. Testing Checklist (for a real environment with network + credentials)

- [ ] `pip install -r requirements.txt` succeeds and pins resolve
- [ ] `POST /dub` with no `tts_engine` field still produces Edge TTS output
      identical to pre-migration (regression check)
- [ ] `GET /tts/engines` returns 6 engines; `edge` and `gtts` show
      `available: true` with zero configuration
- [ ] Set `AZURE_SPEECH_KEY`/`AZURE_SPEECH_REGION` → `azure` flips to
      `available: true`; `POST /dub` with `"tts_engine": "azure"` produces
      audio
- [ ] Set `ELEVENLABS_API_KEY` → same check for `elevenlabs`, including a
      `clone_voice()` call against a short reference sample
- [ ] Force a primary-engine failure (e.g. temporarily invalid Azure key)
      and confirm the response still succeeds via the `gtts` fallback, with
      a warning logged
- [ ] (Optional, non-Render-Free) install `requirements-optional.txt`,
      download a Piper `.onnx` model, set `PIPER_VOICE_MODEL_MAP`, and
      confirm `piper` synthesizes
- [ ] (Optional, non-Render-Free, GPU recommended) confirm `xtts` loads the
      model and clones a voice from a reference `.wav`
- [ ] Full existing pipeline regression: upload → transcribe → translate →
      TTS → mux → download, unchanged end-to-end

---

## 9. Known Risks

- **Version pins are unverified against live PyPI** (no network in this
  sandbox) — see §3.
- **Azure Neural voice names are assumed compatible with Edge's**, since
  both are documented as sharing Microsoft's neural voice backend. This
  wasn't independently re-verified against Azure's current voice list in
  this session; a voice name that's valid on one may not resolve on the
  other. Pass an Azure-specific `voice` explicitly if you hit this.
- **XTTS v2's `supported_languages()` list is from its public model card at
  authoring time** and should be checked against whatever model version is
  actually installed.
- **Piper's exact CLI flags** (`--model`, `--output_file`, `--length_scale`,
  stdin for text) are based on Piper's long-stable documented interface, but
  were not confirmed against a real binary in this sandbox.
- **Per-segment "engine actually used" is not persisted.** If a fallback
  occurs, the manager logs it, but `DubbingTask.tts_engine` still reflects
  what was *requested*, not necessarily what generated every clip. See §10.

---

## 10. Future Extension Points

- **Caching**: `services/tts/cache.py` defines a real `TTSCacheBackend`
  protocol wired into the manager as `NullTTSCache` (always misses). A disk,
  Redis, or S3-backed cache can be dropped in with zero changes anywhere
  else — implement `get()`/`set()` and pass an instance to
  `TTSEngineManager(cache=...)`.
- **Streaming**: `BaseTTSEngine.synthesize_stream()` is a real hook; `edge`
  already implements it for real. ElevenLabs also has a genuine `/stream`
  REST endpoint that could get the same treatment later.
- **Multi-speaker dubbing**: `TTSRequest.speaker` and
  `supports_multi_speaker()` already exist as scaffolding. The real gap is
  upstream — `transcription_service.py`/`SubtitleSegment` has no speaker
  diarization yet, so there's nothing to route per-speaker today.
- **Per-segment engine tracking**: if fallback behavior needs to be visible
  per-clip (not just in logs), add an `engine_used` field to
  `SubtitleSegment` and set it from each `TTSResponse.engine` in
  `synthesize_segments()`.
- **Lip sync**: genuinely out of scope for a TTS migration — it's a
  video/computer-vision pipeline stage, not a synthesis concern. It would
  land as a new `services/lipsync_service.py` and a new
  `PipelineStage.LIP_SYNC`, sitting between audio generation and final mux,
  and would need its own (currently absent) CV dependencies.
- **Voice cloning end-to-end UX**: the engine-level `clone_voice()` hooks
  are real and working (ElevenLabs, XTTS), but there's no API route yet to
  upload a reference sample and get a usable `voice_id`/`speaker_wav` back.
  Would be a new `POST /voices/clone` endpoint using whichever engine's
  `clone_voice()` the caller requests.

---

## 11. Deployment Notes

- **Render Free**: deploy exactly as before — `requirements.txt` alone.
  `edge`, `gtts`, `azure`, and `elevenlabs` all work (the latter two once
  credentials are set); `piper`/`xtts` will correctly report themselves
  unavailable rather than breaking the deploy.
- **Self-hosted / dedicated worker, for Piper or XTTS**: install
  `requirements-optional.txt`, provision a Piper binary + `.onnx` models (for
  Piper) or accept the PyTorch download + a GPU (for XTTS), and set the
  corresponding env vars. See the commented-out block in `Dockerfile` for
  the two extra lines this needs.
- No database migration and no *pre-migration* (original V3.0) env var
  changed meaning. The two global TTS orchestration variables introduced
  earlier in this same session (`TTS_DEFAULT_ENGINE`/`TTS_FALLBACK_ENGINE`)
  were renamed to `DEFAULT_TTS_ENGINE`/`FALLBACK_TTS_ENGINES` in §12, below,
  before this had ever been deployed anywhere -- update any `.env` you may
  have already created from the earlier draft of this document.

---

## 12. Final Change: gTTS as Default + Configurable Ordered Fallback Chain

After initial delivery, an explicit requirement changed the architecture:
**gTTS must be the default engine, Edge must not be.** This section
documents that change on top of everything above, and its own verification
pass, run separately from §7.

**What changed:**
- `TTS_DEFAULT_ENGINE` → renamed **`DEFAULT_TTS_ENGINE`**, default flipped
  from `edge` to **`gtts`**.
- `TTS_FALLBACK_ENGINE` (a single engine) → replaced with
  **`FALLBACK_TTS_ENGINES`**, a comma-separated ORDERED chain (default
  `edge,azure,piper,xtts,elevenlabs`), per an explicit example. Stored as a
  plain string and parsed by `Settings.get_fallback_engines()` rather than
  relying on pydantic-settings' JSON-vs-delimited env parsing, since that
  behavior couldn't be checked against the real package in this
  network-isolated sandbox.
- `TTSEngineManager.synthesize()` now walks `[primary] + fallback_chain`
  (deduplicated, order-preserved) instead of trying one fallback engine,
  skipping each unavailable/failed engine and continuing to the next,
  exactly as specified. The `TTSValidationError` short-circuit from the
  earlier verification round is preserved.
- `GET /tts/engines`: `TTSEngineInfo.is_fallback: bool` →
  **`fallback_rank: Optional[int]`** (1-based chain position, `null` if not
  in the chain); `TTSEnginesResponse.fallback_engine: str` →
  **`fallback_order: List[str]`**. This response shape had no real external
  consumers yet (introduced earlier in this same session), so it was
  cleanly retyped rather than carrying two redundant fields.
- Fixed one real bug caught by a full-tree grep sweep (not by inspection):
  `services/tts_service.py` still referenced the old `TTS_DEFAULT_ENGINE`
  name in a live code path (not just a docstring) — would have raised
  `AttributeError` at runtime. Also found and fixed a stale comment in
  `requirements.txt` claiming Edge was still default (missed by an earlier
  sweep that was scoped to `*.py` files only).
- All docstrings/comments asserting "Edge is default" (in `config.py`,
  `edge_engine.py`, `gtts_engine.py`, `tts_service.py`, `models/task.py`,
  `models/response.py`) were rewritten, not just the functional defaults.

**What did NOT change:** every original V3.0 endpoint, request/response
field, and the additive-only nature of the API surface from §2–§5 all still
hold. Render Free compatibility is untouched (§9, this section's table).

### Verification (this change specifically) — 23/23 checks passed

| # | Check | Result |
|---|---|---|
| 1 | gTTS is the default engine | ✅ `Settings.DEFAULT_TTS_ENGINE == "gtts"` and `TTSEngineManager.default_engine_name == "gtts"`, both asserted directly |
| 2 | Fallback chain is configurable | ✅ default chain confirmed `["edge","azure","piper","xtts","elevenlabs"]`; **also** re-instantiated `Settings` with `FALLBACK_TTS_ENGINES="azure,elevenlabs"` and `DEFAULT_TTS_ENGINE="azure"` and confirmed both take effect independently |
| 3 | Existing API compatibility preserved | ✅ all 9 original routes present; exactly one new route; `DubRequest` still constructs without `tts_engine`; `extra="forbid"` still rejects unknown fields |
| 4 | All imports resolve | ✅ single-entry-point `import app` |
| 5 | FastAPI starts successfully | ✅ real `lifespan()` startup + shutdown |
| 6 | All engines register correctly | ✅ all 6 present; `gtts.fallback_rank is None` (it's the default); `edge.fallback_rank == 1` (first in chain) |
| 7 | End-to-end pipeline works | ✅ **two real scenarios**, not one: (a) in this sandbox, where `gtts` is genuinely not installed, requesting the default engine correctly auto-skipped it and cascaded to `edge`, satisfying "auto-skip unavailable, continue to next fallback" under real conditions; (b) a second Python process with a `gtts` stub installed confirmed the true happy path — default engine succeeds directly, no fallback triggered. Real `ffmpeg`/`ffprobe` re-confirmed audio assembly still works (4.000s output from a 4.0s request). |
| 8 | Render Free compatibility preserved | ✅ Dockerfile unchanged functionally; `requirements.txt` confirmed free of `piper-tts`/`TTS==`/`torch`; confirmed those remain isolated to `requirements-optional.txt` |
| 9 | No regressions | ✅ explicit `engine_name="edge"` still works directly (Edge fully functional as an optional engine); empty-text validation still short-circuits without wastefully walking the whole fallback chain |

One honest limitation carried forward from §7: `gTTS`, `azure-cognitiveservices-speech`, `TTS` (Coqui), and the `piper` binary are still not actually installed in this sandbox (no network). Scenario 7(b) above used a separate, isolated stub specifically to demonstrate the gTTS-succeeds-directly path without contaminating the rest of the suite's honest "gTTS genuinely absent" baseline used everywhere else.

---

## 14. Sprint 2: Core Production Upgrade

New files: `services/audio_processing.py`. Modified: `config.py`, `core/utils.py`,
`core/task_manager.py`, `services/tts_service.py`, `services/tts/manager.py`,
`services/tts/engines/edge_engine.py`, `services/video_merger.py`,
`services/pipeline.py`, `app.py`.

**Audio DSP (`services/audio_processing.py`)** — real FFmpeg filters, each
individually verified against real generated audio before being shipped:
silence trim (`silenceremove`), fade in/out (`afade`), loudness
normalization (`loudnorm`, EBU R128), noise gate (`agate`), click
reduction (`adeclick`), peak limiter (`alimiter`), dynamic compression
(`acompressor`), equalizer (`highpass`/`lowpass`/`equalizer`). All disabled
by default (zero behavior change unless an operator opts in).

One real defect caught by testing, not assumed correct: `silenceremove`'s
`start_duration`/`stop_duration` parameters are *themselves* consumed as
extra trim on top of the detected silence — empirically confirmed across
three values before the default was corrected from 0.3s (would have eaten
real speech) to 0.05s.

**Timeline alignment** — bounded, pitch-preserving time-stretch (`atempo`)
fits an overlong clip to its segment window (default cap: 1.20x). Enabled
by default (a direct fix for a demonstrated issue, not a stylistic
choice). Verified: a clip needing 1.5x compression is correctly capped at
1.2x and honestly reports `fully_fit=False` with the exact residual
overrun; a clip needing only 1.1x fits cleanly.

**Audio ducking (Part 4)** — `sidechaincompress`-based, genuinely reactive
(not fixed time windows): the original track attenuates only while the
dubbed track is actually audible. Measured, not assumed: baseline −21.1dB
→ −31.4dB while dub speech plays → back to exactly −21.1dB the instant it
stops. This is the honest fallback for when true source separation is
unavailable, which is always true on Render Free (a real separation model
is heavy ML, same category of problem as XTTS). Opt-in, off by default.

**Parallel TTS synthesis** — bounded concurrency (`TTS_PARALLEL_WORKERS`,
default 4) replacing the prior strictly-sequential loop, with fail-fast
semantics preserved: the first segment failure cancels remaining in-flight
segments rather than letting them complete pointlessly.

**Resume support** — `TaskManager` gained durable per-task JSON
persistence (it was previously pure in-memory, a real gap found while
implementing this) plus reload-on-startup; `pipeline.py` gained
per-stage skip-if-already-done checks. Verified: a task survives a
simulated process restart with correct field values; a task with
pre-completed stages correctly skips extraction/transcription/translation
without re-invoking any of those services. Honest platform caveat, stated
plainly: this survives a process restart *within the same running
instance*. It does not survive a Render Free redeploy or
spin-down-after-inactivity — both wipe the ephemeral filesystem entirely,
which is a deployment-platform constraint no in-app logic can work around.

**Video merge fix** — `build_dubbed_audio_track` was hardcoding `"aac"`
instead of reading `OUTPUT_AUDIO_CODEC` (Part 6 violation, now fixed), and
`video_merger.py` was re-encoding that already-encoded AAC track a second
time on every merge (confirmed via reading the actual command, not
assumed). Now stream-copies (`-c:a copy`) since both stages are guaranteed
to target the same codec/bitrate by construction.

**Diagnostics** — `synthesize_segment`, `manager._try_engine`, and
`edge_engine.generate` now log the exact exception with a full stack
trace (`exc_info=True`), requested language/voice/engine, and whether a
fallback was engaged — the original ask before Sprint 1/2 arrived,
finished here rather than dropped.

**Verification**: 42 checks across three suites (23 prior-regression +
9 voice-fix-regression + 10 Sprint-2-specific), all passing, plus the
standalone resume-skip test above. One real bug was caught and fixed
during this pass: a test stub producing placeholder (non-decodable) audio
bytes correctly tripped the new, genuine `ffprobe` duration check —
diagnosed as a fixture defect (fixed the stub to emit real audio) rather
than a code defect, since production TTS engines always emit valid audio.

**Scoped out, and why** (per the instruction to only leave something
incomplete if physically impossible, or to state clearly what was built
instead): true ML-based source separation (Part 4's ideal, not its
fallback) needs a heavy separation model in the same weight class as
XTTS — physically incompatible with Render Free's 512MB RAM, exactly like
XTTS. The ducking fallback above is what ships instead; the architecture
is prepared for a real model later via the same lazy-optional-dependency
pattern already used for XTTS/Piper. True chunked processing (splitting
very long videos into independently-processed time segments with clean
re-stitching across chunk boundaries) is a larger architectural change,
not a paid-API/GPU requirement — it was not attempted in this pass rather
than delivered shallow and untested; existing memory safety (all FFmpeg
work is subprocess-streamed, never loaded fully into Python memory) and
bounded concurrency (`TTS_PARALLEL_WORKERS`) are the real mitigations
currently in place for long videos.

---

## 13. Bug Fix: gTTS Failing on an Incompatible Voice

**Reported symptom** (Render end-to-end test): dubbing failed with
`Engine 'gtts' does not support voice selection.`

### Traced call chain (confirmed by reading the actual code, not assumed)

```
app.py:296            task.voice = request.voice
                       (stored with zero engine-awareness)

pipeline.py:139        voice = task.voice or Settings.get_default_voice(target_language)
                       ⚠ broader than reported: this manufactures a non-empty
                        Edge-style voice for EVERY request, even ones with no
                        voice specified at all, independent of task.tts_engine

pipeline.py:141-147    synthesize_segments(..., voice=voice, engine=task.tts_engine, ...)

tts_service.py         TTSRequest(..., voice=voice or None, ...)

manager.py:162 (pre-fix)  response = await engine.generate(request)
                       ⚠ ROOT CAUSE: no check of engine.supports_voice_selection()
                        before this call

gtts_engine.py:56      self.validate_request(request)   # generate()'s first line

base.py:163-165        if request.voice and not self.supports_voice_selection():
                            raise VoiceNotFoundError(f"Engine '{self.name}' does
                            not support voice selection.")
                       -> "Engine 'gtts' does not support voice selection."

manager.py (pre-fix)   VoiceNotFoundError is a TTSValidationError, caught by the
                       existing short-circuit (added for empty-text-style
                       errors) and re-raised immediately -> hard task failure
```

**Responsible layer:** `services/tts/manager.py` — not the API layer, not
`tts_service.py`, not the engine adapter, not configuration. `base.py` and
`gtts_engine.py` were behaving exactly as designed (correctly rejecting an
incompatible request when called directly); the manager simply never
checked engine capability before invoking `generate()`. Scope is broader
than the report suggested: because `pipeline.py:139` always resolves *some*
voice, this affected essentially every gTTS-default dubbing job, not only
ones where a caller explicitly picked a voice.

**Latent twin bug, found and fixed as a side effect:** Piper and XTTS both
also inherit `supports_voice_selection() -> False` and were never given an
override. They had the identical bug, just not yet exercised by the
reported test. A manager-level fix (rather than one special-cased inside
`gtts_engine.py`) resolves all three at once, and any future engine too.

### Fix

`services/tts/manager.py` gained `_request_for_engine()`, called once per
engine attempt inside `_try_engine()`, immediately before
`engine.generate()`:

```python
if request.voice and not engine.supports_voice_selection():
    return dataclasses.replace(request, voice=None)
return request
```

`TTSRequest` is an ordinary (non-frozen) dataclass, so `dataclasses.replace`
returns a new object — the original `request` is never mutated, which
matters for the fallback chain: if `gtts` (voice stripped) fails and the
chain cascades to `edge` (which supports voice selection), `edge`'s attempt
re-checks capability against the *original*, untouched request and
correctly receives the voice back. Verified directly (§ below).

`base.py`'s strict `validate_request()` check was deliberately left
unchanged: it remains correct, protective behavior for any future caller
that invokes an engine's `generate()` directly, bypassing the manager. The
adaptation belongs at the orchestration layer, not by weakening the
engine's own contract.

### Verification — 9/9 new checks, plus the full prior 23-check suite re-run clean (32/32 total)

| Check | Result |
|---|---|
| Exact reported case: default engine (gtts) + `voice="hi-IN-SwaraNeural"` | ✅ succeeds (was: hard failure) |
| **Production scenario**, gtts genuinely installed (isolated stub): serves the exact reported voice **directly**, no fallback | ✅ `engine=gtts success=True`, voice silently dropped |
| Pipeline-manufactured default voice (no voice in the original request at all) + engine forced to gtts | ✅ succeeds without `VoiceNotFoundError` |
| Voice-capable engine (`edge`) still receives the requested voice, unmodified | ✅ confirmed via response metadata |
| `piper` and `xtts` (the latent twin bug) no longer raise `VoiceNotFoundError` for an incompatible voice | ✅ both |
| Fallback-chain correctness: `gtts` (voice stripped) fails → `edge` attempt receives the **original**, unstripped voice | ✅ confirmed via response metadata |
| Regression: empty-text validation still short-circuits immediately (unrelated to this fix) | ✅ unaffected |
| Full prior 23-check suite (default engine, configurable chain, API compatibility, imports, startup, engine registration, real-ffmpeg pipeline, Render compatibility, no regressions) | ✅ 23/23, re-run clean |
| `grep` confirms `engine.generate()` is called from exactly one place in the entire codebase (`manager.py`) | ✅ the fix cannot be bypassed by another code path 
