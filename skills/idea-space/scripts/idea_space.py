#!/usr/bin/env python3
"""A local, transactional idea notebook. Python standard library only."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import uuid


def default_root() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "idea-space"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@contextmanager
def database(root: Path):
    root = root.expanduser().absolute()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = root / "ideas.sqlite3"
    if target.is_symlink():
        raise ValueError("Refusing a symlink database")
    db = sqlite3.connect(target, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            raise ValueError(f"Unsupported database version {version}; no changes made")
        if version == 0:
            if db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                raise ValueError("Unrecognized database; no changes made")
            db.execute("""CREATE TABLE ideas (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, thought TEXT NOT NULL,
                context TEXT NOT NULL, links TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('active','archived','deleted')),
                before_delete TEXT CHECK(before_delete IN ('active','archived')),
                legacy_path TEXT UNIQUE)""")
            db.execute("""CREATE TABLE additions (
                id INTEGER PRIMARY KEY, idea_id TEXT NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
                thought TEXT NOT NULL, context TEXT NOT NULL, links TEXT NOT NULL,
                created_at TEXT NOT NULL)""")
            db.execute("PRAGMA user_version=1")
        db.commit()
        os.chmod(target, 0o600)
        yield db
    finally:
        db.close()


def required(text: str, field: str) -> str:
    if not text.strip():
        raise ValueError(f"{field} must not be empty")
    return text


def get(db, idea_id: str, include_deleted: bool = False) -> dict:
    row = db.execute("SELECT * FROM ideas WHERE id=?", (idea_id,)).fetchone()
    if row is None or (row["status"] == "deleted" and not include_deleted):
        raise ValueError("Idea not found; use list --status deleted to inspect the trash")
    item = dict(row)
    item["links"] = json.loads(item["links"])
    item["additions"] = [dict(a) for a in db.execute(
        "SELECT thought,context,links,created_at FROM additions WHERE idea_id=? ORDER BY id", (idea_id,))]
    for a in item["additions"]:
        a["links"] = json.loads(a["links"])
    return item


def capture(db, title, thought, context="", links=None, legacy_path=None) -> dict:
    required(title, "title")
    required(thought, "thought")
    identity, timestamp = uuid.uuid4().hex, now()
    with db:
        db.execute("INSERT INTO ideas VALUES (?,?,?,?,?,?,?,'active',NULL,?)",
                   (identity, title, thought, context, json.dumps(links or [], ensure_ascii=False),
                    timestamp, timestamp, legacy_path))
    return get(db, identity)


def exclusive_write(destination: Path, content: str) -> None:
    """Publish a complete file without replacing any existing destination."""
    destination = destination.expanduser().absolute()
    if not destination.parent.is_dir():
        raise ValueError("Export parent directory must already exist")
    fd, tmp = tempfile.mkstemp(prefix=".idea-export-", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.link(tmp, destination)
        if os.name == "posix":
            directory = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        os.unlink(tmp)


def markdown(items: list[dict]) -> str:
    chunks = ["# Idea Space export\n"]
    for item in items:
        chunks += [f"## {item['title']}\n", f"ID: {item['id']}\nStatus: {item['status']}\n",
                   "### Original thought\n", item["thought"] + "\n"]
        for label, value in [("Context", item["context"]), ("Links", "\n".join(item["links"]))]:
            if value:
                chunks += [f"### {label}\n", value + "\n"]
        for a in item["additions"]:
            chunks += [f"### Added {a['created_at']}\n", a["thought"] + "\n"]
            if a["context"]:
                chunks.append(a["context"] + "\n")
            if a["links"]:
                chunks.append("\n".join(a["links"]) + "\n")
    return "\n".join(chunks)


def import_backup(db, source: Path) -> dict:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(payload.get("ideas"), list):
        raise ValueError("Expected an Idea Space schema_version 1 JSON export")
    imported, skipped, identities = [], 0, set()
    with db:
        db.execute("BEGIN IMMEDIATE")
        for item in payload["ideas"]:
            fields = ("id", "title", "thought", "context", "created_at", "updated_at", "status")
            if not isinstance(item, dict) or any(not isinstance(item.get(k), str) for k in fields):
                raise ValueError("Invalid idea fields in backup; import rolled back")
            identity = item["id"]
            if len(identity) != 32 or any(c not in "0123456789abcdef" for c in identity) or identity in identities:
                raise ValueError("Invalid or repeated idea ID in backup")
            identities.add(identity)
            required(item["title"], "title")
            required(item["thought"], "thought")
            if item["status"] not in ("active", "archived", "deleted") or (
                item.get("before_delete") not in ("active", "archived") if item["status"] == "deleted" else item.get("before_delete") is not None
            ):
                raise ValueError("Invalid archive/trash state in backup")
            if item.get("legacy_path") is not None and not isinstance(item["legacy_path"], str):
                raise ValueError("Invalid legacy path")
            if not isinstance(item.get("additions"), list):
                raise ValueError("Invalid additions")
            for record in [item, *item["additions"]]:
                if not isinstance(record, dict) or not isinstance(record.get("links"), list) or any(not isinstance(link, str) for link in record["links"]):
                    raise ValueError("Invalid links")
                if any(not isinstance(record.get(k), str) for k in ("thought", "context", "created_at")):
                    raise ValueError("Invalid addition fields")
            if db.execute("SELECT 1 FROM ideas WHERE id=?", (identity,)).fetchone():
                if get(db, identity, True) != item:
                    raise ValueError(f"Conflicting existing ID {identity}; no ideas imported")
                skipped += 1
                continue
            db.execute("INSERT INTO ideas VALUES (?,?,?,?,?,?,?,?,?,?)", (
                identity, item["title"], item["thought"], item["context"], json.dumps(item["links"], ensure_ascii=False),
                item["created_at"], item["updated_at"], item["status"], item.get("before_delete"), item.get("legacy_path")))
            for addition in item["additions"]:
                db.execute("INSERT INTO additions (idea_id,thought,context,links,created_at) VALUES (?,?,?,?,?)", (
                    identity, addition["thought"], addition["context"], json.dumps(addition["links"], ensure_ascii=False), addition["created_at"]))
            imported.append(identity)
    return {"imported": imported, "already_present": skipped}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=default_root(), help="Local storage folder")
    sub = p.add_subparsers(dest="command", required=True)
    for command in ("capture", "append"):
        c = sub.add_parser(command)
        c.add_argument("--title", required=True) if command == "capture" else c.add_argument("id")
        thought = c.add_mutually_exclusive_group(required=True)
        thought.add_argument("--thought")
        thought.add_argument("--thought-file", type=Path, help="Read original UTF-8 text verbatim")
        c.add_argument("--context", default="")
        c.add_argument("--link", action="append", default=[])
    for command in ("list", "find"):
        c = sub.add_parser(command)
        if command == "find":
            c.add_argument("query")
        c.add_argument("--status", choices=["active", "archived", "deleted", "all"], default="active")
    c = sub.add_parser("get")
    c.add_argument("id")
    c.add_argument("--include-deleted", action="store_true")
    for command in ("archive", "unarchive", "delete", "restore"):
        sub.add_parser(command).add_argument("id")
    c = sub.add_parser("export")
    c.add_argument("--id")
    c.add_argument("--format", choices=["json", "markdown"], default="json")
    c.add_argument("--output", type=Path, required=True)
    c = sub.add_parser("purge")
    c.add_argument("id")
    c.add_argument("--confirm-id", required=True)
    c.add_argument("--backup", type=Path, required=True)
    sub.add_parser("import-legacy").add_argument("folder", type=Path)
    sub.add_parser("import-backup").add_argument("file", type=Path)
    return p


def run(args) -> dict | list:
    with database(args.root) as db:
        cmd = args.command
        if cmd == "import-backup":
            return import_backup(db, args.file)
        if cmd in ("capture", "append"):
            thought = args.thought_file.read_text(encoding="utf-8") if args.thought_file else args.thought
            required(thought, "thought")
            if cmd == "capture":
                return capture(db, args.title, thought, args.context, args.link)
            with db:
                db.execute("BEGIN IMMEDIATE")
                get(db, args.id)
                db.execute("INSERT INTO additions (idea_id,thought,context,links,created_at) VALUES (?,?,?,?,?)",
                           (args.id, thought, args.context, json.dumps(args.link, ensure_ascii=False), now()))
                db.execute("UPDATE ideas SET updated_at=? WHERE id=?", (now(), args.id))
            return get(db, args.id)
        if cmd == "get":
            return get(db, args.id, args.include_deleted)
        if cmd in ("list", "find", "export"):
            with db:
                db.execute("BEGIN")
                items = [get(db, row[0], True) for row in db.execute("SELECT id FROM ideas ORDER BY created_at,id")]
                if cmd == "export":
                    if args.id:
                        items = [get(db, args.id, True)]
                    payload = {"schema_version": 1, "ideas": items}
                    data = markdown(items) if args.format == "markdown" else json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
                    exclusive_write(args.output, data)
                    return {"exported": len(items), "path": str(args.output.absolute())}
                items = [i for i in items if args.status == "all" or i["status"] == args.status]
                if cmd == "find":
                    query = args.query.casefold()
                    items = [i for i in items if query in json.dumps(
                        {k:i[k] for k in ("title", "thought", "context", "links", "additions")}, ensure_ascii=False).casefold()]
                return [{k:i[k] for k in ("id", "title", "status", "created_at", "updated_at")} for i in items]
        if cmd in ("archive", "unarchive", "delete", "restore", "purge"):
            with db:
                db.execute("BEGIN IMMEDIATE")
                item = get(db, args.id, True)
                if cmd == "purge":
                    if item["status"] != "deleted" or args.confirm_id != args.id:
                        raise ValueError("Purge requires a deleted idea and its exact --confirm-id")
                    exclusive_write(args.backup, json.dumps({"schema_version": 1, "ideas": [item]}, ensure_ascii=False, indent=2) + "\n")
                    db.execute("DELETE FROM ideas WHERE id=?", (args.id,))
                    return {"purged": args.id, "backup": str(args.backup.absolute())}
                if cmd == "restore":
                    if item["status"] != "deleted":
                        raise ValueError("Only deleted ideas can be restored; use unarchive for archived ideas")
                    status, previous = item["before_delete"], None
                elif cmd == "delete":
                    if item["status"] == "deleted":
                        return item
                    status, previous = "deleted", item["status"]
                else:
                    if item["status"] == "deleted":
                        raise ValueError("Restore a deleted idea before changing its archive status")
                    status, previous = ("archived" if cmd == "archive" else "active"), None
                db.execute("UPDATE ideas SET status=?,before_delete=?,updated_at=? WHERE id=?", (status, previous, now(), args.id))
            return get(db, args.id, True)
        if cmd == "import-legacy":
            folder = args.folder.expanduser().resolve(strict=True)
            imported, skipped = [], 0
            for source in sorted(folder.rglob("idea.md")):
                if source.is_symlink() or not source.resolve().is_relative_to(folder):
                    raise ValueError("Legacy source escapes its selected folder")
                key = str(source.resolve())
                if db.execute("SELECT 1 FROM ideas WHERE legacy_path=?", (key,)).fetchone():
                    skipped += 1
                    continue
                original = source.read_text(encoding="utf-8")
                title = next((l[2:] for l in original.splitlines() if l.startswith("# ")), source.parent.name)
                imported.append(capture(db, title, original, "Imported legacy idea.md verbatim; original files retained", legacy_path=key)["id"])
            return {"imported": imported, "already_imported": skipped, "source_unchanged": True}
    raise ValueError("Unknown command")


def main(argv=None) -> int:
    try:
        print(json.dumps(run(parser().parse_args(argv)), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"idea-space: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
