# Validation and remaining device work

This is a functional development build, not a verified Steam Deck release.

## Automated checks

- Python: 29 passing tests covering authentication, local-model allowlist, errors, response mapping, context/model/game cache isolation, fallback policy, dictionary readings/forms, TSV escaping, idempotent saves, encounters, screenshot consent/selective deletion, and mocked AnkiConnect including refusal of an unrelated service.
- Frontend: four passing tests covering single-flight immersion requests, cancellation, restart generations, polling limits, and upstream OCR grouping/filtering with Japanese fixtures.
- Strict TypeScript and production builds pass. Four upstream TypeScript errors were fixed without replacing its OCR, capture or input implementations.
- Synthetic 1280×800 game scenes cover normal dialogue, vertical text, partial dialogue, mixed UI, stylized dialogue, repeated text and damaged OCR. Generated screenshots stay in ignored test output. These checks validate transport and fixture geometry, **not OCR engine accuracy**.
- The ZIP includes the frontend, backend/providers, GPLv3 license, notices and checksum-verified upstream Linux dependencies. It excludes Windows binaries, credentials, models, databases and screenshots.

```powershell
.venv/Scripts/python.exe -m pytest -q
node --test tests/frontend.test.cjs
pnpm run typecheck
pnpm run build
.venv/Scripts/python.exe tools/package_plugin.py
```

## Workbench measurements

Measured 2026-10-25 with Ollama 0.40.11 on an i5-1135G7 (4 cores/8 threads), 11.8 GiB usable RAM and Intel Iris Xe. Ollama reported CPU inference and zero GPU offload. Initial free RAM was about 0.8 GiB; Windows reclaimed memory during testing. No unrelated applications were closed. Peak working set includes Ollama and its worker processes, not total committed memory.

The fixture set has six short translation requests (including a repeat) and one damaged OCR request, preserved with an `[Unclear OCR]` marker without inference. Warm statistics exclude the damaged input and first cold request. Timings include localhost/measurement overhead, not Deck OCR, Wi-Fi or rendering.

| Model | Cold | Warm range | Peak RAM | Observation |
|---|---:|---:|---:|---|
| Qwen3 0.6B | 2.74 s | 0.54–0.84 s | 0.81 GiB | Reversed “don't go alone” into “I'll go alone”; rejected as default |
| Qwen3 1.7B | 5.42 s | 0.82–1.36 s | 1.59 GiB | Faster, but awkward phrasing and context errors |
| Qwen3 4B | 10.44 s | 1.92–3.06 s | 2.72 GiB | Final default: context support and one model for both tasks |
| TranslateGemma 4B | 11.49 s | 2.19–2.82 s | 3.40 GiB | Good short translations; documented prompt omits dialogue history |

[Raw synthetic results](benchmarks/) include inputs, outputs, timing and memory; [summary.json](benchmarks/summary.json) contains computed statistics. Outputs were inspected for meaning, negation, incompleteness and invented information. This small qualitative comparison is not a formal accuracy score or native-speaker evaluation. Both 4B models inferred possessors for 約束 where Japanese leaves them implicit. Multi-region screens take longer because regions are translated sequentially.

Earlier Qwen runs with ambiguous JSON input failed schema validation. Final v3 runs use an explicit English instruction and constrained response schema. Earlier memory readings that omitted workers were discarded. The real plugin HTTPS client was tested against the gateway with its token and certificate pin: Qwen3 4B returned English with the original rectangle in 11.56 seconds cold; a repeat took 127 ms. Live Sudachi/JMdict analysis, deterministic grammar, vocabulary saving and targeted cleanup passed. No commercial translation endpoint participated. The gateway currently runs on loopback; a LAN rule and Deck pairing are still required.

Grammar trials exposed errors: Qwen 1.7B took 6.5 s but ended mid-explanation; 4B took 24.0 s and misdescribed ないで. Common constructions now use deterministic notes and incomplete model output is rejected. Other explanations remain tentative. Readings/definitions always come from Sudachi/JMdict.

## Actual OCR fixture run

`tools/benchmark_ocr.py` ran the existing RapidOCR engine against seven generated 1280×800 scenes on Workbench. RapidOCR 3.8.3 and ONNX Runtime 1.26.0 match the versions in the Linux plugin archive, though this measurement uses Windows wheels and one CPU thread. Engine initialization took 1.26 s; the first recognition took 1.39 s and subsequent scenes 0.60–0.96 s. These are not Steam Deck timings.

Four scenes exactly matched their source after Unicode/whitespace normalization. Vertical Japanese lost its final punctuation; the partial line lost one ellipsis; mixed UI read `/` as `ノ`. All boxes remained within the original screen. The synthetic damaged character survived recognition and is handled as uncertain text by the translation service. See [raw OCR results](benchmarks/rapidocr-workbench.json) for every output, confidence, rectangle and model hash. These simple Yu Gothic scenes do not represent real game typography or a general OCR accuracy score.

To reproduce separately from the server environment:

```powershell
.venv/Scripts/python.exe -m venv .local/ocr-venv
.local/ocr-venv/Scripts/python.exe -m pip install rapidocr==3.8.3 onnxruntime==1.26.0 Pillow==13.0.0
.local/ocr-venv/Scripts/python.exe tools/benchmark_ocr.py --download
```

A Japanese font is required (`--font` can select one). This Workbench's system Microsoft C++ runtime was too old for ONNX; the run used `--dll-dir <portable-Ollama-directory>/lib/ollama/vulkan` to load the Microsoft runtime shipped with the verified Ollama download, without changing system DLLs. ONNX still ran on CPU. This optional OCR test environment is not used by the translation server and is not packaged for the Deck. Generated PNGs remain ignored local files.

## Steam Deck LCD acceptance checklist

1. Install the ZIP using Decky Developer mode. Confirm **Dross Deck Translator** has independent settings. Disable one plugin's shortcut if upstream is also installed.
2. Pair using the gateway URL, token and TLS fingerprint. Verify the installed model in Test Connection. Wrong tokens and fingerprints must fail.
3. Select Japanese → English, Dross Local AI and Chrome Screen AI. Download its OCR engine. Repeat later with RapidOCR. Keep Local providers only enabled.
4. Open a Japanese game at 1280×800. Use the shortcut shown in Controls (code default: L5). Time shortcut-to-English. Check rectangle alignment, scaling and dock/undock.
5. Test horizontal dialogue, separated boxes, vertical columns, incomplete lines, mixed UI, decorative fonts, repeats and poor OCR. Multi-column vertical reading order is unverified; fixture coverage is not proof of recognition accuracy.
6. Test Japanese, English and bilingual modes, long lines and font scaling. Dismiss and verify gameplay resumes, with Pause Game on Overlay both on and off.
7. In Study, navigate sentence/word selectors with D-pad and A. Check readings/forms, save a word and export TSV. Test B and Resume game. Verify buttons do not trigger game actions beneath the modal; pause manually until input isolation is confirmed.
8. Disconnect Workbench. Without fallback, expect a connection error. With NLLB downloaded and enabled, expect an on-device fallback notification. Confirm no cloud calls. Reconnect and retry.
9. Configure AnkiConnect separately. Use Save + Anki twice on one selection and verify one updated note in `Japanese::Game Immersion::<game>`. Close Anki and confirm local saving still works. Test screenshot saving with both privacy switches off, one on and both on.
10. Start Immersion at 15 seconds and close QAM within two seconds. Static frames should skip OCR; repeated text should skip translation. New dialogue should update live subtitles without a frozen background or overlay appearing in the next capture. Test Steam/QAM menus for accidental recognition.
11. Stop using its button, dismiss shortcut, plugin disable and game exit. No further captures should begin; an in-flight inference may finish but must not reopen the overlay. Test suspend/resume and game switches for stale context.
12. Measure FPS, CPU, battery drain, network volume, OCR time and gateway latency for ten minutes. Increase polling interval if needed. These device measurements are outstanding.

## Remaining roadmap

- Physical SteamOS acceptance is the release gate: QAM visibility guards, input isolation, suspend/resume and composition need validation.
- Extend vertical ordering based on real OCR failures, not guessed layouts.
- Expand reviewed grammar rules and add native-speaker evaluation before relying on model explanations.
- Add optional local vision inference. Current image transmission supports explicit vocabulary screenshots only; translation remains text-only.
- Improve multi-region latency with validated batch translation and tune polling from battery measurements.
- Verify real AnkiConnect/media cards; add a history browser, dictionary sense selection and finer deletion controls.

## References

The [upstream](https://github.com/cat-in-a-box/Decky-Translator) remains GPLv3. Inference follows [Ollama chat](https://docs.ollama.com/api/chat), [TranslateGemma's prompt guide](https://ollama.com/library/translategemma), and [Qwen3](https://ollama.com/library/qwen3). Windows setup follows [Ollama's documentation](https://docs.ollama.com/windows). Tokenization uses [SudachiPy](https://github.com/WorksApplications/sudachi.rs/tree/develop/python); dictionary attribution follows [EDRDG](https://www.edrdg.org/edrdg/licence.html).
