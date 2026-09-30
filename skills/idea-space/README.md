# Idea Space

A local notebook for ideas that are not commitments. Capture original text, find it later, append without replacing it, archive, export, trash and recover it. No account, network, cloud memory or project creation is involved.

Requires Python 3.10+ (standard library) and persistent local storage. From this folder:

```
python3 scripts/idea_space.py capture --title 'A thought' --thought 'Keep the original wording'
python3 scripts/idea_space.py list
python3 scripts/idea_space.py find 'word'
python3 scripts/idea_space.py export --output /existing/folder/new-backup.json
```

Data goes to `$XDG_DATA_HOME/idea-space/ideas.sqlite3`, falling back to `~/.local/share/idea-space/ideas.sqlite3`. All commands accept `--root <folder>` before the command. Use the same folder from every project. Existing directories retain their permissions; new store directories use owner-only permissions on POSIX systems. SQLite transactions and a ten-second busy timeout protect concurrent writes. No app lock or encryption is provided. OS permissions and disk encryption remain host responsibilities.

## Recovery

`delete ID` is recoverable trash. `restore ID` restores its earlier archive state. `archive ID` hides an idea from the active list; `unarchive ID` makes it active again. `list --status all` includes archived and deleted ideas.

Create a JSON export before moving hosts or changing the store. It includes original text, additions, IDs, timestamps, context, links and trash/archive state. Export destinations must be new files in an existing folder. Markdown export is readable but is not the restore format.

`import-backup new-backup.json` restores a JSON export into the selected store. Identical existing records are skipped; conflicts or invalid records roll back the complete import. It does not fetch stored links or interpret their contents. Recovering a trash record retains trash status until `restore ID`.

`purge ID --confirm-id ID --backup /existing/folder/new-recovery.json` requires the record to be in trash, saves a complete recovery export before removing it from the live database, and refuses to overwrite backup files. It is not secure deletion: recovery exports, OS backups and SQLite disk remnants can retain data. Remove retained files only when explicitly desired.

`import-legacy <explicit-folder>` imports legacy `idea.md` files verbatim, retaining the original files and attachments. Repeating it skips the same original paths; it does not update earlier imports. Do not delete the legacy folder as part of migration. The compatibility `capture_idea.py` entrypoint now writes the portable SQLite notebook and keeps only explicitly supplied old metadata as context.

## Verification

```
python3 -m unittest discover -s tests -v
```

Tests use temporary synthetic stores only, including concurrent writers, Unicode, backup recovery, conflict rollback, failed exports, future-schema refusal, symlinks and non-destructive legacy import. macOS/Python execution is recorded in the review package. Other compatible local hosts are supported by the standard-library design but require their own host smoke check. Cloud ChatGPT persistence and cross-device synchronization are not implemented.

`PRIVACY.md` is a publication draft. Before directory submission the publisher must publish that policy, provide its live URL, and complete identity/rights/terms checks described in the review report.
