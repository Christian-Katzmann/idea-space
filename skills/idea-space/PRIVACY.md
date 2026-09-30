# Idea Space privacy policy

## Scope

This policy covers the reviewed Idea Space plugin package version 1.0.0. It does not describe other versions or tools. Publication of this policy does not by itself announce a software release.

Idea Space stores only ideas the user chooses to capture: title, original text, optional context and links, additions, timestamps, IDs and archive/trash state. Legacy import also records the original file path to avoid duplicates. It does not collect contacts, credentials, payment details, device identifiers, location, or other personal data automatically. Do not put secrets or restricted personal data in the notebook.

The bundled Python program performs no network requests or telemetry. Data remains in the chosen local SQLite folder, defaulting to `$XDG_DATA_HOME/idea-space` or `~/.local/share/idea-space`. Exports and recovery backups are stored at user-selected paths. No data is sent to the developer. The agent host may process conversation text and tool results under that host's separate policy; filesystem backups/sync are controlled by the user and OS.

Stored ideas remain until the user removes them. Archive hides rather than deletes. Delete moves to local trash. Restore recovers it. Purge removes a trashed record from the live store only after creating a recovery file, which remains until the user removes it. SQLite remnants and OS backups may retain data; this tool does not promise secure erasure. Users can list, retrieve, export, restore, and delete their records locally without an account or developer assistance.

No notebook contents need to be shared for support. Use synthetic examples and redact local paths if sharing diagnostics.

## Publisher and contact

Publisher: Christian Katzmann. Effective date: September 30, 2026. For private privacy or support requests, contact [christian@katzmann.dk](mailto:christian@katzmann.dk). Send a minimal description; do not include credentials, notebook contents, production records or raw traces. Any information you choose to send for support is processed in the publisher's existing email service to answer that request, and remains until the correspondence is deleted. Request deletion through the same address. Provider backups and mandatory retention, if applicable, can outlast live-mailbox deletion.
