<div align="center">
  <img src="VibeHUD/Assets.xcassets/AppIcon.appiconset/icon_256x256.png" alt="vibe hud icon" width="120" height="120">
  <h1 align="center">vibe hud</h1>

  <p align="center">
    A native macOS notch HUD for Claude Code, Codex, and other AI coding agents. Follow sessions, review supported tool requests, and reply from one place.
  </p>

[![GitHub Star](https://img.shields.io/github/stars/section9-lab/VibeHUD?style=rounded&color=white&labelColor=000000)](https://github.com/section9-lab/VibeHUD/stargazers)
[![GitHub license](https://img.shields.io/github/license/section9-lab/VibeHUD?style=rounded&color=white&labelColor=000000)](LICENSE)
[![Release Version](https://img.shields.io/github/v/release/section9-lab/VibeHUD?style=rounded&color=white&labelColor=000000)](https://github.com/section9-lab/VibeHUD/releases/latest)
![GitHub Repo size](https://img.shields.io/github/repo-size/section9-lab/VibeHUD?style=rounded&color=white&labelColor=000000&label=dmg%20size)

[![Kofi](https://img.shields.io/badge/Kofi-Jack-orange.svg?style=flat-square&logo=kofi)](https://ko-fi.com/jackvibe)
[![Patreon](https://img.shields.io/badge/Patreon-Jack-red.svg?style=flat-square&logo=patreon)](https://www.patreon.com/jack)

</div>

## Demo

<p align="center">
  <img src="docs/assets/vibe-hud-demo.gif" alt="Animated macOS notch demo showing agent rings, active session counts, menu bar app icons kept visible to the right of the hardware notch when the HUD is collapsed, and sessions from Claude Code, Codex, WorkBuddy, and Cursor" width="1000">
</p>
<p align="center"><sub>Simulated macOS desktop with sample sessions.</sub></p>

## What it does

vibe hud brings local AI coding sessions into your Mac’s notch. Follow Claude Code, Codex, and other supported agents while they continue to work in their own environments. The HUD shows session activity and conversation history, and can handle supported tool requests and replies. Available actions depend on the agent, its events, and the terminal setup.

[Website](https://hud.vibevibe.cc/) · [Download](https://hud.vibevibe.cc/download/) · [Setup guides](https://hud.vibevibe.cc/docs/) · [Compatibility](https://hud.vibevibe.cc/docs/compatibility/)

## Product highlights

- Monitor multiple Claude Code, Codex, and other supported agent sessions
- See session activity and open local conversation history in the HUD
- Review supported tool requests and approve or deny them from the notch
- Answer supported Claude `AskUserQuestion` prompts and send replies through compatible terminal routes
- Enable integrations for Cursor, GitHub Copilot, Pi, OpenCode, WorkBuddy, and Qwen Work from Agent Hooks
- Works with tmux, Terminal.app, iTerm2, and Ghostty
- Choose your display, sound, Claude directory, and startup behavior
- Built-in update checks and installs through Sparkle

## Main workflows

### Stay on top of active sessions

vibe hud follows supported Claude Code and Codex session events and keeps important state visible: running work, waiting input, tool requests, and recently active sessions.

### Handle approvals faster

When Claude needs permission to use a tool, vibe hud brings the approval flow to the notch so you can allow or deny it immediately.

### Reply without context switching

When a session needs an answer, you can respond from the HUD instead of manually hunting for the right terminal pane.

### Review conversations in one place

You can open a session view to see history, follow progress, and keep track of what Claude has been doing.

## Requirements

- macOS 15.6+
- A supported coding agent installed and configured, such as Claude Code or Codex

## Install

Download the latest release from the GitHub releases page and move `VibeHUD.app` into `/Applications`.

Open the notch menu, expand **Agent Hooks**, and enable the integration you use. Start a fresh agent session after enabling it. On subsequent launches, vibe hud refreshes hooks that were already enabled; installing the app alone does not enable every integration.

For setup and troubleshooting, see the [Claude Code guide](https://hud.vibevibe.cc/docs/claude-code/) and [Codex guide](https://hud.vibevibe.cc/docs/codex/).

Release downloads:
- https://github.com/section9-lab/VibeHUD/releases/latest

## Settings

From the notch menu, you can configure:

- preferred screen
- notification sound
- Claude config directory
- launch at login
- hooks on or off
- update checks and installs

## Compatibility

vibe hud supports several local agent integrations and can route replies through the environments it detects, including:

- bridge mode
- tmux
- Terminal.app
- iTerm2
- Ghostty
- accessibility fallback when needed

Available requests, replies, and focusing features depend on the agent, emitted events, and your environment. Terminal focusing can benefit from tmux and optional window-management tooling. See the [agent and terminal compatibility guide](https://hud.vibevibe.cc/docs/compatibility/) for the current scope.

## Claude directory support

vibe hud works with the current Claude config layout and can resolve the config directory from:

1. `CLAUDE_CONFIG_DIR`
2. the directory you pick in vibe hud
3. `~/.config/claude`
4. `~/.claude`

## Updates

vibe hud uses Sparkle for in-app updates, so installed builds can check for new versions and install them from the app.

GitHub tag releases require the `SPARKLE_PRIVATE_KEY` Actions secret matching `SUPublicEDKey` in `VibeHUD/Info.plist`. The workflow signs each DMG and verifies its signature against the built app's public key before publishing. Keep this key pair across releases.

Older builds without an update public key may need a one-time manual reinstall to establish trust in signed updates. Their in-app updater cannot accept a release that changes both the app signing identity and the update signing key.

## Privacy

The app reads local session events and conversation history to display the HUD. It also uses Mixpanel for app launches and session starts, with an app-generated identifier and metadata such as app, build, macOS, and Claude Code versions. The analytics events in the current source do not attach conversation text. See the [privacy page](https://hud.vibevibe.cc/privacy/) for details.

## Build from source

For a release-style local build:

```bash
./scripts/build.sh
```

To package a notarized release DMG:

```bash
./scripts/create-release.sh
```

## Tests

Run the native Swift test suite with Xcode:

```bash
xcodebuild test -project VibeHUD.xcodeproj -scheme VibeHUD -destination 'platform=macOS' CODE_SIGNING_ALLOWED=NO
```

The Python hook adapter, OpenCode JavaScript plugin, and release packaging contract retain focused runtime tests because those components execute outside the Swift process.

Run `bash tests/test_update_signature.sh` to verify acceptance of signed archives and rejection of modified archives, missing or mismatched keys, and incorrect release metadata.

## License

Apache 2.0
