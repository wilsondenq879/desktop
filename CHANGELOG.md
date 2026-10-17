# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-10-17

### Fixed

- Server visual patch: Renderer 6.2 / Guard 13.2. Correct hub/port spacing, split distributed logical group regions, preserve CJK IDs, wrap labels at final card width, and render up to 48 ports without negative dimensions.
- Validate the complete decorated SVG before PNG export. Retry bounded alternate layouts; if a global view cannot satisfy the unchanged quality gates, emit explicitly labelled focused connection views retaining all canonical nodes, edges and directions.
- Separate missing model data from actual renderer errors. Preserve real artifacts when optional UI notifications/diagnostics fail; retain grounded early text when the short preface pass times out. Details and limits: `docs/ARCHITECTURE_RELIABILITY.md`.

### Verification

- 40 real PNG/SVG/HTML topology cases plus one forced fallback pass final geometry/composition checks; notification/disconnected-UI and chart/report regressions also pass. Live verification uses two models and regenerates the original failed conversation without deleting older answers. This is evidence for the documented valid-input range, not an unconditional uptime guarantee.

## [0.0.33] - 2026-10-09

### Added

- **Fireworks 技術架構圖 Skill.** Open WebUI now ships the complete Fireworks Tech Graph 1.2.0 runtime (schemas, templates, SVG renderer, quality checks, PNG/HTML export paths, and MIT attribution), not only a prompt. Architecture, topology, GPU/RDMA, API/MCP, and technical workflow requests now route to this Skill first and produce previewable project artifacts.
- **Native Fireworks renderer Tool.** Architecture requests can now invoke a server-side Tool that creates a per-request Fireworks SVG artifact, attaches it to the chat, and reports progress through compact status updates.
- **Technical architecture diagram Skill.** Open WebUI now includes a native `技術架構圖設計` Skill for network topology, AI/GPU/RDMA systems, layered software architecture, API/MCP integration, and technical flows. It defines device types, architecture zones, semantic connections, and strict factual-quality rules.
- **Server-side Skill semantic routing.** A global inlet Filter uses the configured local multilingual embedding model plus conservative keyword and intent scoring to load the one or two most relevant Skills before inference. Explicit `/Skill` selections remain authoritative, and per-user modes support automatic, suggest-only, or manual behavior.

### Changed

- **One architecture renderer at a time.** The legacy inline React+SVG protocol remains a fallback, but no longer competes with or overrides Fireworks when the semantic router selects it.
- **Architecture-quality responsive diagrams.** React + SVG cards now understand hardware roles, grouped zones, bidirectional paths, and vertical or horizontal hierarchy. Desktop shows full architecture groupings while phone layouts automatically become readable vertical topologies instead of shrinking every layer into one row.

### Fixed

- **No diagram source in streamed chat.** The retired `openwebui-diagram` JSON contract is no longer injected for Fireworks requests. While an architecture is rendering, users see only a concise drawing status; completed responses contain the SVG artifact rather than JSON, Mermaid, or source code.
- **Diagrams no longer share one generic card.** The renderer chooses a Fireworks visual family for network/RDMA, hardware, software, cloud, API, workflow, or clean architecture diagrams instead of rendering all topics through the same topology template.
- **Model picker labels stay in the picker.** Capability icons now appear only for the available choices after opening the model menu; the compact selected-model control in the composer remains uncluttered.
- **Renderable technical diagrams for every model.** Open WebUI now has a server-side global Filter that asks technical architecture, networking, RDMA, hardware-connection, and comparison questions to use the React + SVG diagram protocol rather than Mermaid or ASCII—even for models without a custom per-model prompt.
- **React + SVG diagram cards.** The local Open WebUI web frontend now turns a constrained `openwebui-diagram` JSON response into a responsive, zoomable SVG card. This replaces fragile Mermaid parsing and is shared by browser and mobile WebView sessions.

## [0.0.32] - 2026-10-09

### Added

- **Model capability icons.** The existing Open WebUI model picker is now decorated with compact, accessible icons for capabilities such as reasoning, vision, coding, Tools, and image generation. Server metadata takes priority; conservative local-model recognition is only used when metadata is unavailable.

### Changed

- **One server control on mobile.** The duplicate top-right server settings shortcut was removed. The top-left server menu remains the single place to switch or manage saved Open WebUI servers, while refresh remains separate.

## [0.0.31] - 2026-10-09

### Fixed

- **Reliable native Skill sync.** The desktop importer now accepts both direct and nested Open WebUI Workspace list responses (including `data.items`), preventing valid local Skills from being mistaken for an empty server list and keeping them available to companion clients.

## [0.0.29] - 2026-10-07

### Added

- **Open WebUI Workspace Skills sync.** Desktop now imports the bundled and local Codex/Agents/Claude `SKILL.md` files into Open WebUI's native Workspace Skills API, so they appear in the built-in `$` picker instead of only existing in a local Codex directory.
- **Draw Things directly from chat.** Desktop exposes a local `draw_image` tool that calls the Draw Things HTTP API on this computer or another device on the LAN, then returns the generated image to the active Open WebUI conversation.
- **Project-aware image output.** Every generated image is saved under `generated-images` in the chat's selected project or isolated temporary workspace. When signed in, Desktop also uploads the image to the same Open WebUI account so it remains visible from other devices.
- **Draw Things settings.** A dedicated settings page includes enable/disable controls, the API address, connection testing with explicit feedback, Mac auto-launch, and Windows-to-Mac LAN setup guidance.

### Security

- **Stable skill IDs.** Existing `lmlab-*` IDs are preserved for compatibility while their visible names drop the `lmlab` prefix. Skill sync is additive and does not replace or delete unrelated Workspace Skills.
- **Loopback-only bridge.** The Desktop image bridge listens only on `127.0.0.1`, requires a per-launch bearer key for tool calls, validates image parameters, and serves fallback artifacts through opaque filenames.

## [0.0.28] - 2026-10-07

### Fixed

- **New chats no longer inherit another chat's folder.** A project chosen before a chat exists is now a one-shot selection claimed only by that new chat. Existing chats without a saved project receive their own isolated workspace instead of falling back to another chat's pending folder.
- **Safe temporary workspaces.** Starting without a project creates an isolated Desktop-managed folder for that chat. Choosing a permanent project later moves the generated files there without overwriting existing files; naming conflicts are preserved under a safe alternate name.
- **Clear temporary state in the UI.** The project launcher, status bar, and workspace panel identify temporary workspaces and explain that choosing a project will move the files automatically.

## [0.0.27] - 2026-10-07

### Added

- **Project launch home.** Desktop connections now open with a project-first start screen, including the selected folder, recent projects, workspace readiness, and an explicit chat-only option.
- **Progress / Changes / Artifacts workspace.** A persistent right panel follows each project task from its automatic pre-change checkpoint through completion, then groups detected file changes and generated artifacts.
- **Change review and one-click restore.** Text changes can be reviewed side by side in the built-in Canvas. A recoverable restore action returns protected files to their pre-task versions and moves newly created files into the checkpoint backup.
- **Artifact Canvas.** Images, PDFs, HTML, and text artifacts can be previewed without leaving Desktop; Office and unsupported formats open in their installed Windows application.

### Changed

- **Desktop requests are checkpointed automatically.** When a project folder is active, Desktop captures a bounded local snapshot before sending the model request and scans the project again after the streamed response completes.

## [0.0.26] - 2026-10-07

### Fixed

- **Desktop login state now stays synchronized.** The embedded Open WebUI securely relays token changes on page load, sign-in, sign-out, focus, and SPA navigation, while project actions also perform an immediate sync before registering local tools.
- **Removed the false signed-out project error.** A delayed login-token relay no longer marks an otherwise working Desktop project folder as failed. Direct local file tools remain attached to each request while personal terminal registration retries after the token becomes available.
- **Responses no longer look frozen before the first token.** When stock Open WebUI only shows a blinking caret, Desktop now presents a compact activity state with a truthful waiting message, elapsed time, and a longer-wait hint. Native search and tool statuses continue to take precedence.

## [0.0.25] - 2026-10-07

### Fixed

- **Project folder works from the first message.** Selecting a project folder now starts Open Terminal with that folder as its root working directory before the embedded WebUI loads. The first request is prepared before it leaves Desktop, and its local file tools are restored even if Open WebUI's initial localhost discovery happened too early.
- **Generated files default to the selected folder.** Desktop requests explicitly tell the model to create and verify artifacts in the chosen project folder without asking for another save location or falling back to browser-only instructions.
- **Approval mode is enforced.** The control beside `＋` now also sets Open WebUI's native tool approval parameter (`要求核准` / `代我核准`) instead of relying only on an instruction message.

## [0.0.24] - 2026-10-07

### Changed

- **Approval control beside `＋`.** `要求核准` and `代我核准` now live in their own compact control immediately beside the message composer’s `＋` button. The selected policy is included with model requests without changing the message you wrote.
- **Native Skills restored.** Removed the Desktop slash picker and all desktop-specific Skills-folder scanning. Open WebUI’s own Skills and `/` behaviour are left untouched, so LMLab and future imported Skills remain independently selectable.

## [0.0.23] - 2026-10-06

### Added

- **Imported Skills in Slash Picker.** The `/` picker now scans Codex, Agents, Open WebUI, LMLab, and user-selected folders for `SKILL.md` files every time it opens. Imported skills can be searched and inserted directly into the chat.
- **Writing Mode Choice.** Choose `自動改檔` to instruct the model to apply project changes without pausing, or `先問我` to inspect first and request approval before a write.

## [0.0.22] - 2026-10-06

### Added

- **Desktop Skills.** Type `/` in the Open WebUI message box to choose `/fix`, `/implement`, `/review`, or `/test`. `/fix` and `/implement` instruct the model to modify the selected project through the available tools and report the files and verification actually completed.

## [0.0.21] - 2026-10-06

### Added

- **Choose Project Before Chat.** Select a Windows project folder from the Desktop status bar before creating a conversation. The next new chat receives that folder automatically, while existing chats keep their own project selection.

### Changed

- **Reliable Windows x64 Packages.** Windows installer and portable builds now use the bundled Node-API terminal binaries, allowing them to be packaged from macOS without rebuilding native code.

## [0.0.20] - 2026-05-07

### Fixed

- **Blank Webview on Linux.** Replaced the `--in-process-gpu` Chromium flag with SwiftShader software rendering (`--use-gl=angle --use-angle=swiftshader`). The in-process GPU flag broke `<webview>` guest compositing entirely, leaving connection views blank on all Linux configurations. SwiftShader keeps the GPU process out-of-process (required for webview compositing) while avoiding driver-level crashes (#178).

## [0.0.19] - 2026-05-06

### Fixed

- **Spotlight Pulls to First Desktop on macOS.** Spotlight no longer switches Spaces when triggered from a non-primary desktop. The window is now visible on all workspaces, and `app.focus({ steal: true })` — which activated the entire app and caused the Space switch — has been replaced with targeted window-level focus (#179).
- **Gray Screen When Connecting to Server on Linux.** Replaced the `--disable-gpu` Chromium flag with `--in-process-gpu`, which keeps the display compositor alive so `<webview>` guest surfaces actually paint instead of showing a gray rectangle. The previous flag fixed GPU process crashes but broke webview rendering on Debian and Ubuntu (#178).
- **Open Terminal Fails Silently Without Python.** Open Terminal now automatically installs Python when it's missing instead of throwing an opaque error. Progress status is surfaced in the UI during installation.
- **Corrupt Auto-Update Manifests.** Fixed the release workflow to deduplicate artifact entries during manifest merging, preventing SHA512 checksum mismatches that caused updates to fail silently.

## [0.0.18] - 2026-05-05

### Fixed

- **Downloaded Models Not Recognized by llama.cpp.** Models downloaded from Hugging Face are now stored directly under the `models/` directory instead of a nested `models/huggingface/` subdirectory, so llama-server's model scanner discovers them without manual symlinks. Existing models in the old location are automatically migrated on startup (#177).

## [0.0.17] - 2026-05-03

### Added

- **Webview Context Menu.** Right-clicking inside the webview now shows a native context menu with Cut, Copy, Paste, Undo/Redo, spell-check suggestions, and "Open Link in Browser" — enabling system autofill and password manager integration on login pages (#161).

### Changed

- **Windows OpenSSL Compatibility.** The bundled Python's directory is now prepended to `PATH` on Windows so its own OpenSSL DLLs are loaded before any conflicting system-wide installations (Git for Windows, Anaconda, Strawberry Perl, etc.), preventing the `OPENSSL_Uplink: no OPENSSL_Applink` crash on startup (#167).
- **Links Open in Default Browser on Windows.** Added `allowpopups` to the webview so that `target="_blank"` link clicks correctly propagate to the main process handler and open in the default browser instead of being silently blocked (#165, #170).
- **Linux System Requirements.** Documentation now specifies glibc 2.28+ as a minimum requirement for Linux installations.

## [0.0.16] - 2026-05-02

### Fixed

- **Links Open in Default Browser.** Clicking links in chat responses now opens them in the user's default browser instead of navigating within the app or spawning a new Electron window (#165).

## [0.0.15] - 2026-04-28

### Added

- **ARM64 Support for Linux and Windows.** Native ARM64 builds are now produced for Linux (.deb, AppImage) and Windows (NSIS installer), enabling support for Raspberry Pi, NVIDIA DGX Spark, Snapdragon laptops, and other ARM64 devices (#140).

### Fixed

- **Grey/Blank Screen on Linux.** Disabled GPU compositing entirely on Linux to prevent shared memory allocation crashes that caused a grey or blank screen on systems with restricted `/dev/shm` or `/tmp` permissions.
- **Spotlight Dismiss Behavior.** Pressing Escape or the toggle shortcut to dismiss Spotlight no longer erroneously brings the main application window to the foreground (#158).

## [0.0.14] - 2026-04-28

### Fixed

- **Grey/Blank Webview on Linux.** Disabled GPU compositing on Linux to prevent silent compositor failures that produce a grey rectangle instead of rendered content on systems with problematic Intel/NVIDIA drivers or certain Wayland compositors (#119).
- **Renderer Crash Recovery.** The main window now automatically reloads when the renderer process dies unexpectedly, preventing a permanent blank/grey screen.
- **Webview Crash Diagnostics.** Added logging for guest webview renderer crashes to aid debugging connectivity and rendering issues.
- **macOS Notarization.** Resolved Apple notarization failure caused by an expired Developer Program agreement, restoring signed and notarized macOS builds.

## [0.0.13] - 2026-04-27

### Fixed

- **Copy Button on Linux (GNOME/Wayland/Flatpak).** Fixed the "Copy" button in the Open WebUI interface not actually writing to the system clipboard on Linux. The webview session was missing the `clipboard-sanitized-write` permission required by Electron for `navigator.clipboard.writeText()` to work.

## [0.0.12] - 2026-04-25

### Added

- **Toggleable Clipboard Auto-Paste for Spotlight.** Spotlight's automatic clipboard pasting is now optional and can be toggled in Settings, so the input bar starts empty when preferred.
- **Persistent Window Size and Position.** The app now remembers your window dimensions, position, and maximized state across restarts, with safe fallback when a saved display is disconnected.

### Fixed

- **Linux .deb Crash.** Fixed app failing to launch on Linux with `Failed to load native module: pty.node` by enabling native module rebuilds and unpacking node-pty from the asar archive during packaging.
- **Grey Screen on Connection Failure.** The webview now shows an error overlay with retry and open-in-browser options instead of a blank grey screen when a connection fails to load or crashes.
- **Global Shortcuts on Wayland/Flatpak.** Global shortcuts now work on Wayland desktops via `xdg-desktop-portal`, with clear user-facing notifications when a shortcut cannot be registered.

## [0.0.11] - 2026-04-24

### Fixed

- **macOS Launch Crash.** Fixed app failing to launch with "different Team IDs" error by adding the missing `disable-library-validation` entitlement to the build signing configuration.
- **Self-Signed SSL Connections.** The app now trusts all SSL certificates, allowing connections to Open WebUI instances behind self-signed or untrusted certificates without errors.

## [0.0.10] - 2026-04-24

### Added

- **Concurrent Model Downloads.** Multiple Hugging Face models can now be downloaded simultaneously, each with independent progress tracking and per-file cancel buttons.

### Changed

- **Models Settings UI.** Cleaner layout with inline progress bars, hover-reveal download buttons, and breadcrumb-style repo navigation.

### Fixed

- **GPU Process Crash Recovery.** The app now automatically detects GPU process crashes (common with certain NVIDIA/Intel drivers on Windows) and relaunches with the GPU sandbox disabled, instead of closing immediately. No manual shortcut edits required.

## [0.0.9] - 2026-04-20

### Fixed

- **Open Terminal API Key Persistence.** The Open Terminal API key is now saved in config.json and reused across restarts instead of being regenerated on every startup, which was breaking existing integrations.

## [0.0.8] - 2026-04-11

### Added

- **Voice Input.** System-wide push-to-talk voice transcription. Press the shortcut from any app to record audio, which is automatically transcribed and sent to your active chat.
- **Voice Input Settings.** Configurable global hotkey and enable/disable toggle in Settings, with a default of Shift+Cmd+Space (macOS) or Shift+Ctrl+Space (Windows/Linux).
- **Audio Feedback.** Bundled start and stop chime sounds play when recording begins and ends.

### Fixed

- **Shortcut Recorder on macOS.** Shortcut inputs now use physical key codes instead of character values, fixing Alt key combinations producing unicode characters like √ instead of V.

## [0.0.7] - 2026-04-11

### Fixed

- **macOS Auto-Update.** Auto-update now works correctly on macOS. Previously, the updater tried to download a zip file with a versioned filename that did not exist in the release.

## [0.0.6] - 2026-04-10

### Added

- **Spotlight Screenshot Capture.** Drag anywhere on the Spotlight overlay to select a region of your screen. Screenshots appear as inline thumbnails and are sent alongside your message.
- **Multiple Screenshots.** Attach several screenshots in a single Spotlight query. Each one can be individually removed before sending.
- **Click-to-Dismiss Spotlight.** Clicking the background outside the input bar dismisses Spotlight, in addition to pressing Escape.
- **Screen Recording Permission Prompt (macOS).** If screen capture permission hasn't been granted, a notification guides you to the correct System Settings page.
- **Screenshot Hint.** A "Drag anywhere to capture a screenshot" hint appears when Spotlight opens.
- **Offline Mode for llama.cpp.** Previously downloaded llama.cpp binaries are automatically detected on startup, so local models work without an internet connection.
- **Auto-Connect on Startup.** The app pre-connects to your default connection when launched, so Spotlight queries work immediately.

### Changed

- **Fullscreen Spotlight Overlay.** Spotlight now opens as a fullscreen transparent overlay on your active display rather than a small floating window, enabling screenshot capture and multi-display support.
- **Faster Remote Connections.** Switching to a remote server is now instant with no loading delay.
- **Smarter Loading Indicator.** The loading spinner only appears when the local server is actually starting, instead of showing on every connection switch.
- **Clearer Sidebar Selection.** Active connections are more visually distinct with bolder text and stronger highlights. Inactive connections are subtler for better contrast.
- **Safer llama.cpp Updates.** The app verifies internet connectivity before removing the current installation, preventing accidental data loss when updating offline.

### Fixed

- **Tray Menu Connections.** Clicking a connection from the system tray menu now correctly opens it in the app.
- **Dark Mode Context Menus.** Sidebar right-click menus no longer appear incorrectly highlighted in dark mode.
- **Local Server Always Accessible.** The local connection in the sidebar is no longer grayed out when the server isn't running. Clicking it will start the server.
- **Open Terminal Install Errors.** If automatic installation of Open Terminal fails, you now see a clear error message instead of a silent failure.
- **Network Timeout Handling.** Requests for llama.cpp releases now time out after 10 seconds instead of hanging indefinitely on slow networks.

## [0.0.5] - 2026-04-07

### Added

- **Two-Way Theme Sync.** Theme changes in Open WebUI are now mirrored to the desktop app and vice versa, so your light/dark preference stays consistent everywhere.
- **Seamless Spotlight Queries.** Spotlight prompts now appear directly in your already-open chat without triggering a full page reload.

### Fixed

- **Auto-Default Connection.** Selecting a connection now automatically saves it as your default for Spotlight and app startup.
- **Smooth Connection Switching.** Switching between already-open connections no longer causes unnecessary page reloads.
- **Connection Switch Race Condition.** Clicking a remote connection while the local server is still starting no longer gets overridden when the local server finishes loading.

## [0.0.3] - 2026-04-06

### Fixed

- **Spotlight Focus.** Spotlight now reliably appears after interacting with the main window. Previously could fail to show on macOS.
- **Spotlight Search Passthrough.** Searches submitted from Spotlight now correctly load in already-open connections instead of being silently ignored.

## [0.0.2] - 2026-04-06

### Added

- **Spotlight Input Bar.** Lightweight quick-chat bar (⇧⌘I) for submitting queries without opening the full app.
- **Spotlight Shortcut.** Dedicated configurable shortcut for Spotlight, independent from the global app shortcut.
- **Draggable Spotlight.** Spotlight bar can be dragged to any position on screen.
- **Persistent Spotlight Position.** Spotlight position is saved and restored across app restarts.
- **Spotlight Settings.** Shortcut recorder in Settings → General for the Spotlight shortcut.

### Fixed

- **System Theme Sync.** The app now responds to OS dark/light mode changes in real-time when set to "Auto". Previously only checked once at startup.

## [0.0.1] - 2026-03-20

### Added

- **Local Server Management.** Install, start, stop, and restart Open WebUI directly from the desktop app.
- **Connection Manager.** Connect to multiple Open WebUI servers with sidebar quick-switch.
- **Status Bar.** Real-time status indicators for Open WebUI, Open Terminal, and llama.cpp services.
- **Log Viewer.** Live terminal log viewer for all services with copy, refresh, and resize.
- **Open Terminal Integration.** Built-in terminal server for AI-powered shell access.
- **llama.cpp Integration.** Local inference engine with model management and Hugging Face downloads.
- **Settings.** General, Open WebUI, Terminal, Inference, Models, Connections, and About panels.
- **Global Shortcut.** Configurable system-wide hotkey to bring the app to the foreground.
- **Auto-Update.** Built-in update checker with one-click download and install.
- **Tray Support.** System tray icon with quick actions and optional background mode.
- **Factory Reset.** One-click removal of all installed components, data, and connections.
- **Disk Space Check.** Pre-install check requiring at least 5 GB of free storage.
- **Internationalization.** English, Japanese, Chinese (Simplified & Traditional) translations.
- **In-App Changelog.** Accessible from the About settings page.
- **Cross-Platform.** macOS, Windows, and Linux support.
