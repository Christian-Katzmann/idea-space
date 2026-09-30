# Idea Space

![Idea Space](assets/icon.png)

Give your ideas a place to grow without interrupting your work. Capture the original thought, add context later and find it again when you're ready. Search your collection, build on an idea without replacing the original, and bring it back when the time is right.

## Install

Use the portable plugin ZIP with a compatible local skill host. The package contains `plugin.json` and `skills/idea-space/SKILL.md`. If your host requires a host-specific installation flow, follow that host’s plugin instructions. Directory listing and OpenAI review are not yet complete.

Requires Python 3.10 or later and a persistent local filesystem. There is no hosted service or cloud synchronization.

## Use

Ask your coding assistant: “Save this thought in Idea Space without starting work.” The local notebook supports capture, search, append, archive, export, trash, restore and backup-protected purge. See [the skill guide](skills/idea-space/README.md) for command examples and storage controls.

Capturing an idea does not authorize implementation, research, reminders or external messages. Purging a record creates a recovery file; this is not secure erasure.

## Privacy and license

Ideas stay in the selected local notebook. Your coding host may process prompts and tool results under its own policy. Read the [privacy policy](PRIVACY.md) before use. For private support: christian@katzmann.dk. Do not send notebook contents or secrets.

Copyright © 2026 Christian Katzmann. Original code, instructions and documentation are licensed under [MIT](LICENSE). User notebook contents remain the user’s.
