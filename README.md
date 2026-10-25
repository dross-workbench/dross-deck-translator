# Dross Deck Translator

A GPLv3 fork of [cat-in-a-box/Decky-Translator](https://github.com/cat-in-a-box/Decky-Translator), with an authenticated local Ollama gateway on Windows. The original project and copyright notices are retained below.

Development branch: `feat/dross-local-immersion`. The fork has its own Decky identity, settings, temporary files and cache. Local-only mode is enabled by default; it blocks commercial OCR/translation providers. No paid AI API is required.

## Connect Steam Deck to Workbench

For the Workbench already prepared during development, Python dependencies, Ollama, the four evaluated models and JMdict are installed. The gateway currently listens on loopback only. Run `server/Configure-Connection.ps1 -BindAddress <WORKBENCH_PRIVATE_IP>` to retain those files and generate a certificate for its LAN address, restart the Dross server, then continue with step 3. The firewall rule and automatic startup have not been enabled.

1. Use Python 3.12 or 3.13 on Windows. From the repository, run `server/Install-Server.ps1 -Python <python-executable> -BindAddress <WORKBENCH_PRIVATE_IP>`. This installs the server and portable Ollama, generates a token and a TLS certificate, and protects the private configuration with a Windows ACL. To reuse Ollama, pass `-OllamaPath <ollama.exe> -ModelsPath <models-directory>`. The default bind address is loopback for initial testing.
2. Run `server/Start-Server.ps1`, then `server/Pull-Models.ps1` in another terminal. Only the gateway uses the LAN. Ollama remains on localhost with cloud features disabled and one model loaded at a time.
3. In an Administrator PowerShell, run `server/Enable-Lan.ps1 -TrustedDevice <STEAM_DECK_PRIVATE_IP>`. The rule permits only that device, the gateway port, and the Windows Private network profile. Reserve both devices' addresses in your router. Never forward this port through your router.
4. Read `server/.local/config.json` locally. In Decky, install `out/Dross.Deck.Translator.zip` using Settings → Developer → Install Plugin from ZIP. Open **Dross Deck Translator → Dross** and enter `https://<WORKBENCH_PRIVATE_IP>:18765`, the token, and the certificate fingerprint. Press **Save & Test Connection**. Keep the configuration file private.
5. In Translation, select Japanese → English, Chrome Screen AI or RapidOCR, and **Dross Local AI**. Download the selected OCR engine using its existing download button. No screenshots leave the Deck during translation.
6. Run a game. Hold the shortcut configured in Controls to translate; use the same shortcut's dismiss action to return to play. The fork retains the upstream controller behavior (the code defaults to L5; verify your binding in Controls). Choose English, Japanese, or bilingual display in Dross settings.

Optional: download NLLB in Translation and enable **On-device fallback**. A fallback notification is shown; there is no automatic cloud fallback. To start Workbench after Windows sign-in, run `server/Enable-Autostart.ps1`; remove it with `-Remove`. Regenerating a certificate requires re-pairing its fingerprint on the Deck.

## Study and vocabulary

Run `server/Install-Study.ps1` once on Workbench, then restart the gateway. It installs SudachiPy and indexes JMdict locally. Select **Study** mode in the Dross tab; the shortcut opens a sentence selector, word selector, readings, dictionary forms, definitions and particle notes. Grammar generation is a separate button. **Study last screen** also opens the most recent recognition. B or **Resume game** dismisses the study dialog. Controller focus and whether game input leaks through the modal still need SteamOS testing; pause the game manually when studying until verified.

**Save vocabulary** records only the selected item, its game identifier and example sentence on Workbench. Repeated saves retain examples and encounter counts. Run `server/Export-Vocabulary.ps1` for an Anki-compatible UTF-8 TSV in `server/.local/`. Import with tab separator and HTML enabled; map the named columns to your note fields. The first field is a stable ID for duplicate detection. Dictionary data is JMdict © EDRDG under CC BY-SA 4.0, downloaded separately and attributed in the UI and export. Readings come from Sudachi, not the language model. Names and contextual senses can still be ambiguous.

Optional AnkiConnect: install Anki and the AnkiConnect add-on yourself, keep its listener on `127.0.0.1:8765`, add `"anki_enabled": true` to the private Workbench configuration and restart the gateway. **Save + Anki** creates or updates a `Dross Game Immersion` note in `Japanese::Game Immersion::<game ID>`. If Anki fails, the local vocabulary save still succeeds and the error is shown. Existing Anki cards are not deleted when Workbench history is deleted. AnkiConnect has been tested with a mocked localhost API; a working Anki instance has not been verified on this Workbench. Another Python process already occupies its usual port; resolve that conflict without stopping unrelated services.

To include a screenshot, enable **Allow saved screenshots** on the Deck, set `"allow_screenshots": true` in Workbench's private configuration, restart the gateway, capture a new screen, and explicitly select **Include screenshot in this save** in Study. Only that save uploads an image; translation always uses text. Saved PNGs have metadata removed. The Dross tab offers confirmed deletion of Workbench vocabulary, examples and screenshots. Turning off encounter tracking stops recording later occurrences of previously saved words.

Common grammar patterns use deterministic notes. Other contextual model explanations remain experimental: the small model benchmarks produced grammatical errors. Dictionary definitions are never sourced from those explanations.

## Immersion (experimental)

Choose **Immersion** in Dross settings and use **Start immersion** or the translation shortcut. Close the quick-access menu before the two-second startup delay ends. A game must be running and Pause Game on Overlay must be disabled. The default is one capture every 15 seconds after the previous request finishes, configurable from 5 to 60 seconds. Identical frames skip OCR; unchanged recognized text skips translation. Translated labels appear over the live game, with the captured image hidden. Dismiss, Stop immersion, plugin disable, game exit or a request failure stops the loop. An already-running Workbench inference may finish, but its cancelled result is ignored. Polling never resumes automatically after plugin reload. Battery savings and Gaming Mode composition/input behavior are not yet measured on a Deck.

## Build and verify

```powershell
pnpm install --frozen-lockfile
pnpm run typecheck
node --test tests/frontend.test.cjs
pnpm run build
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe tools/package_plugin.py
```

Packaging verifies and includes the upstream Linux dependency archive, including the portable Python runtime. Windows dependencies are never put into the Deck ZIP. Initial OCR/model downloads still need internet; subsequent inference is local.

Milestones have passed automated API/provider/cache/study/history tests, frontend polling/OCR-fixture tests and strict TypeScript validation. A real authenticated HTTPS request through the Deck-side provider produced English with Qwen3 4B on Workbench, preserved its rectangle, and reused the result in 127 ms. Live dictionary analysis, vocabulary saving and targeted cleanup also passed. SteamOS capture, controller behavior and overlay rendering require physical Steam Deck testing and are **not yet verified**. See [TESTING.md](TESTING.md) for measured results and the exact device checklist.

Workbench audit: i5-1135G7 (4 cores/8 threads), 11.8 GiB usable RAM, Intel Iris Xe integrated graphics. Ollama used CPU inference (zero VRAM offload). Final default: **qwen3:4b for both translation and optional analysis**, so one model serves both jobs and supports recent dialogue context. Its five warm short-line requests took about 1.9–3.1 s; cold was 10.4 s, with 2.72 GiB peak process-tree working set. TranslateGemma 4B is available by setting `translation_model` in private configuration; it took 2.2–2.8 s warm, 11.5 s cold and 3.40 GiB, and its documented prompt omits history. The 0.6B model reversed a negative imperative, so it is not recommended. These are small synthetic samples, not a full accuracy evaluation or Deck end-to-end latency. The server keeps no unsaved translation history; the plugin uses memory caching unless disk caching is enabled. Vocabulary storage is opt-in.

## Upstream documentation and attribution

The following original documentation describes upstream functionality, including optional cloud providers. Those providers are blocked while this fork's local-only setting is enabled.

<p align="center">
  <img src="assets/readme-logo.png" alt="Decky Translator" />
</p>

![GitHub Release](https://img.shields.io/github/v/release/cat-in-a-box/Decky-Translator)
![License](https://img.shields.io/github/license/cat-in-a-box/Decky-Translator?color=green)
![Build Status](https://img.shields.io/github/actions/workflow/status/cat-in-a-box/Decky-Translator/build.yml)

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/alexanderdev)

A [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin that lets you translate any text on your Steam Deck screen.

It captures your screen, recognizes text using OCR, translates it and then shows the result with screen overlay.

Might be helpful for learning a new language by playing games or some other purposes (you tell me!).

![Screenshot](assets/screenshot_1.jpg)

![Translation Demo](assets/translation.gif)

## Requirements

- Steam Deck (LCD or OLED)
- Experimental support for non-steamOS handhelds and distros
- [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) installed
- Internet connection required for web-based providers and for initial download of offline models

## Installation

### From Decky Plugin Store
1. Install [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader/tree/main?tab=readme-ov-file#-installation) on your Steam Deck
2. Press <picture><source media="(prefers-color-scheme: dark)" srcset="assets/icons/light/qam.svg"><img height="16" alt="QAM" src="assets/icons/dark/qam.svg"></picture> to open the side bar and go to the Decky tab <picture><source media="(prefers-color-scheme: dark)" srcset="assets/icons/light/plug.svg"><img height="16" alt="Decky" src="assets/icons/dark/plug.svg"></picture>
3. In the upper right corner press <picture><source media="(prefers-color-scheme: dark)" srcset="assets/icons/light/store.svg"><img height="16" alt="Store" src="assets/icons/dark/store.svg"></picture> to view all the available plugins
4. Search for "Decky Translator" and install it

### Manual Installation
1. Install [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader/tree/main?tab=readme-ov-file#-installation) on your Steam Deck
2. [Download](https://github.com/cat-in-a-box/Decky-Translator/releases/latest/download/Decky.Translator.zip) the latest release from the [Releases](https://github.com/cat-in-a-box/decky-translator/releases) page
3. Upload *Decky.Translator.zip* archive to any directory on your Steam Deck
4. Press <picture><source media="(prefers-color-scheme: dark)" srcset="assets/icons/light/qam.svg"><img height="16" alt="QAM" src="assets/icons/dark/qam.svg"></picture>, go to the Decky tab <picture><source media="(prefers-color-scheme: dark)" srcset="assets/icons/light/plug.svg"><img height="16" alt="Decky" src="assets/icons/dark/plug.svg"></picture> and click <picture><source media="(prefers-color-scheme: dark)" srcset="assets/icons/light/gear.svg"><img height="16" alt="Settings" src="assets/icons/dark/gear.svg"></picture>
5. Enable "Developer Mode" in General tab
6. Open the Developer tab
7. Install Plugin from ZIP file -> "Browse" and then select *Decky.Translator.zip*

## How to use it?

1. Press "Translate" button in the main tab of the plugin
2. Press <picture><source media="(prefers-color-scheme: dark)" srcset="assets/icons/light/qam.svg"><img height="16" alt="QAM" src="assets/icons/dark/qam.svg"></picture> to open the menu again and press "Close Overlay"

## How to quickly use it?

1. Hold L4 button for a Quick Translation
2. Hold L4 button again to disable the translation overlay

Button or Combinations can be configured in the Controls tab

## How does it do that? 

Decky Translator allows you to choose different Text Recognition and Translation methods - feel free to experiment.

### Text Recognition (OCR)

| Provider                                                                                               | Type      | Description                                                                                            | Requirements              |
|--------------------------------------------------------------------------------------------------------|-----------|--------------------------------------------------------------------------------------------------------|---------------------------|
| [**Chrome Screen AI**](https://source.chromium.org/chromium/chromium/src/+/main:services/screen_ai/)   | On-device | OCR using Chromium's screen-ai library. The best recognition quality available                         | One-time 120 MB download  |
| [**RapidOCR**](https://github.com/RapidAI/RapidOCR)                                                    | On-device | OCR using PP-OCRv5 ONNX models. Alternative solution for on-device recognition                         | One-time 75 MB download   |
| [**Gemini Vision**](https://ai.google.dev/gemini-api)                                                  | Web       | Recognition and translation in a single API call. Best for stylized/in-game text, but is not very fast | Internet + API key        |
| [**OCR.space**](https://ocr.space/)                                                                    | Web       | Free EU-based Cloud OCR API with some usage limitations. Good choice if you don't translate very often | Internet                  |
| [**Google Cloud Vision**](https://cloud.google.com/vision)                                             | Web       | High accuracy and speed. Great for complex text. Has a great free tier, but requires some setup        | Internet + API key        |

### Translation

| Provider                                                                                     | Type      | Description                                                                                                                          | Requirements                |
|----------------------------------------------------------------------------------------------|-----------|--------------------------------------------------------------------------------------------------------------------------------------|-----------------------------|
| [**NLLB-200**](https://huggingface.co/facebook/nllb-200-distilled-1.3B)                      | On-device | Meta's NLLB-200 1.3B distilled model running locally via CTranslate2. Fully offline after download                                   | One-time 1.4 GB download    |
| [**Gemini Vision**](https://ai.google.dev/gemini-api)                                        | Web       | When Gemini is selected as the OCR provider, it returns the translation in the same call — no separate translation provider needed   | Internet + API key          |
| [**Google Translate**](https://translate.google.com/)                                        | Web       | It's Google. And it translates                                                                                                       | Internet                    |
| [**Google Cloud Translation**](https://cloud.google.com/translate)                           | Web       | High quality translations                                                                                                            | Internet + API key          |


**Note:** Google Cloud and Gemini require an API key but offer a generous free tier for personal use.

<details>
<summary><h2>How to get Google Cloud API key?</h2></summary>


### Step 1: Create a Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" at the top, then "New Project"
3. Give your project a name (any name would work) and click "Create"

### Step 2: Enable Required APIs
1. Go to [APIs & Services > Library](https://console.cloud.google.com/apis/library)
2. Search for and enable:
   - **Cloud Vision API**
   - **Cloud Translation API**

### Step 3: Create an API Key
1. Go to [APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials)
2. Click "Create Credentials" > "API Key"
   - *Authenticate API calls through a service account*: keep unchecked
   - Application Restrictions: None
3. Copy your new API key
4. If you need to find this API key later - press "Show key" button

![API-Key-page](assets/google-cloud-key-1.jpg)
![API-Key-modal](assets/google-cloud-key-2.jpg)


### Step 4: (Optional) Restrict Your API Key
For security, you can restrict the API key to only the Vision and Translation APIs:
1. Click on your API key in the Credentials page
2. Under "API restrictions", select "Restrict key"
3. Select "Cloud Vision API" and "Cloud Translation API"
4. Click "Save"

![API-Key-Restriction](assets/google-cloud-key-4.jpg)

### Step 5: Add API Key to Plugin
1. Open the Decky Translator plugin on your Steam Deck
2. Go to the Translation tab
3. Select Google Cloud Vision and/or Google Cloud Translation as your providers
4. Click "Set Key"
5. Enter your Google Cloud API key
6. Click "Save"

### API Key usually looks like this (but you should have your own):
![API-Key-SteamOS](assets/google-cloud-key-3.jpg)

### IMPORTANT: NEVER SHARE THIS API KEY WITH ANYONE!

### Pricing Note
Google Cloud offers a free tier that should be sufficient for personal use:
- **Vision API**: First 1,000 units/month free
- **Translation API**: First 500,000 characters/month free

**From my own experience**, even everyday usage of Decky Translator with Google Cloud for both recognition and translation rarely goes beyond their free tier. 
Only once I had to pay around 1€/month - and that was during VERY active development and testing phase. 

**But if you want to stay on the safe side anyway** - you could set up a budget limit and notification in [Billing > Budgets & Alerts](https://console.cloud.google.com/billing/budgets)

![API-Key-Budget](assets/google-cloud-key-5.jpg)


</details>

<details>
<summary><h2>How to get Gemini API key?</h2></summary>

Gemini Vision uses a separate key from Google Cloud — it comes from Google AI Studio, not the Cloud Console.

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API key" and pick a project (or let it create one for you)
4. Copy the key
5. In the plugin, open the Translation tab, select **Gemini Vision** as the OCR provider, click "Set Key", paste it, and Save

</details>

## Troubleshooting

### Black screen on capture
Try triggering translation again. If persistent, reboot your Steam Deck

### Translated text is too small
Try increasing the "Font Scaling" option in plugin settings

### Plugin says I'm using a wrong API key
Double-check that you entered it correctly. If the issue persists, please raise an issue - let's investigate it together

### I see nothing / Recognition is bad / It does not translate anything
Try other combination of text recognition and translation methods. If it doesnt solve the problem - please report it here [New Issue](https://github.com/cat-in-a-box/Decky-Translator/issues/new). It will also help if you attach your .log file there

## To-Do
### Functional
- [x] Add offline OCR functionality
- [x] Fix interface scaling issues on non-default SteamOS values (experimental)
- [x] Rework temporary files solution
- [x] Gamepad support
- [x] Overlay font scaling for large monitors
- [x] Fully offline Translation functionality
- [x] Support for non-SteamOS distros
- [ ] Disable in-game buttons while overlay is active
- [ ] Desktop mode support
- [ ] Nicer look for translation overlay
- [ ] TTS for translated text (press the translated label to listen)

## Third-Party Dependencies

This plugin uses the following third-party components. None of the heavy models are bundled in the plugin zip — they're downloaded on demand by a user.

### Chrome Screen AI library

The default on-device OCR engine that provides very impressive results. 
The shared library libchromescreenai.so and its TFLite models are pulled from Google's CIPD server on demand.

| Component | Source | License |
|-----------|--------|---------|
| libchromescreenai.so + TFLite models | [chromium/third_party/screen-ai](https://source.chromium.org/chromium/chromium/src/+/main:services/screen_ai/) via CIPD | BSD-3-Clause (Chromium) |

### RapidOCR Models (PP-OCRv5)

On-device OCR alternative. Based on [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) models (Apache 2.0), exported to ONNX format.

- Text Detection + Chinese Recognition: [MeKo-Christian/paddleocr-onnx](https://github.com/MeKo-Christian/paddleocr-onnx)
- Chinese Dictionary + per-language Recognition models: [monkt/paddleocr-onnx](https://huggingface.co/monkt/paddleocr-onnx) (Apache 2.0)
- Text Classifier: [SWHL/RapidOCR](https://huggingface.co/SWHL/RapidOCR) (Apache 2.0)

| File | Purpose |
|------|---------|
| ch_PP-OCRv5_mobile_det.onnx | Text detection model (shared across all languages) |
| ch_rec.onnx + ch_dict.txt | Chinese/Japanese/English recognition |
| english_rec.onnx + english_dict.txt | English recognition |
| latin_rec.onnx + latin_dict.txt | Latin script (French, German, Spanish, etc.) |
| eslav_rec.onnx + eslav_dict.txt | East Slavic (Russian, Ukrainian) |
| korean_rec.onnx + korean_dict.txt | Korean recognition |
| greek_rec.onnx + greek_dict.txt | Greek recognition |
| thai_rec.onnx + thai_dict.txt | Thai recognition |
| ch_ppocr_mobile_v2.0_cls_infer.onnx | Text direction classifier |

### NLLB-200 Translation Model

Used for offline translation. Downloaded on demand from Hugging Face.

| Component | Source | License |
|-----------|--------|---------|
| NLLB-200 1.3B distilled (CT2 int8 conversion) | [JustFrederik/nllb-200-distilled-1.3B-ct2-int8](https://huggingface.co/JustFrederik/nllb-200-distilled-1.3B-ct2-int8) | CC-BY-NC 4.0 (Meta NLLB-200, **non-commercial use only**) |

The NLLB-200 weights are licensed by Meta for non-commercial use. The plugin does not redistribute them — the user downloads them directly from Hugging Face on demand.

### Python Packages (from PyPI)

| Package | License | Purpose |
|---------|---------|---------|
| Pillow==11.2.1 | MIT-CMU | Image processing for screenshot handling |
| requests==2.32.3 | Apache 2.0 | HTTP library for API calls |
| urllib3==2.4.0 | MIT | HTTP client (dependency of requests) |
| rapidocr>=3.6.0 | Apache 2.0 | OCR engine that runs the PP-OCRv5 ONNX models |
| onnxruntime>=1.7.0 | MIT | ONNX model inference runtime |
| ctranslate2>=4.5.0 | MIT | Inference engine for the NLLB-200 model |
| sentencepiece>=0.2.0 | Apache 2.0 | Tokenizer used by NLLB-200 |
| protobuf>=6.33.1 | BSD-3-Clause | Used by Chrome Screen AI for the inference protocol |

### Bundled Python Runtime

A portable Python 3.13 interpreter is bundled so the plugin works on distros where the system Python doesn't match (Bazzite, etc.). 
Pulled from [astral-sh/python-build-standalone](https://github.com/astral-sh/python-build-standalone), SHA256-verified in CI.

| Component                              | License                                                                     |
|----------------------------------------|-----------------------------------------------------------------------------|
| CPython 3.13 (python-build-standalone) | PSF-2.0, plus various component licenses (see python-build-standalone repo) |

### Web Fonts

Loaded from CDN on demand for the translated text overlay. Not bundled in the plugin.

| Source                                                                                                                                         | License                     |
|------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------|
| [Google Fonts](https://fonts.google.com/) (Open Sans, Montserrat, Noto Sans, Lexend, Atkinson Hyperlegible Next, Andika, etc.)                 | SIL Open Font License (OFL) |
| [OpenDyslexic](https://opendyslexic.org/) (via [@fontsource/opendyslexic](https://www.npmjs.com/package/@fontsource/opendyslexic) on jsDelivr) | SIL Open Font License (OFL) |


## Support

If you find this plugin useful - feel free to buy me a cup of coffee ❤️

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/alexanderdev)

## Thanks to

- [Valve](https://www.valvesoftware.com/) for creating the Steam Deck - a beautiful device that makes projects like this possible
- [UGT (Universal Game Translator)](https://github.com/SethRobinson/UGT) by Seth Robinson for inspiration and the idea of using game translation as a language learning tool
- [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) team for the plugin framework
- [Steam Deck Homebrew](https://github.com/SteamDeckHomebrew) community for their amazing plugins, which served as a great reference while building this one
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR), [RapidOCR](https://github.com/RapidAI/RapidOCR) and [MeKo-Christian](https://github.com/MeKo-Christian/paddleocr-onnx) for OCR engine, OCR models and ONNX model exports that make offline text recognition possible
- [Chromium project](https://www.chromium.org/) for the screen-ai library
- [Meta AI](https://ai.meta.com/) for the NLLB-200 translation model
- [OpenNMT/CTranslate2](https://github.com/OpenNMT/CTranslate2) for the inference engine and [JustFrederik](https://huggingface.co/JustFrederik) for int8 conversion
- [OCR.space](https://ocr.space/) for the free OCR API
- [Google](https://google.com/) for Vision, Translation and Gemini API
- [astral-sh/python-build-standalone](https://github.com/astral-sh/python-build-standalone) for the portable Python runtime
- [steam3d](https://github.com/steam3d) for the SteamOS UI icons
- And You. Yes, You
