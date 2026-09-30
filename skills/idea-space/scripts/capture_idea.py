#!/usr/bin/env python3
"""Compatibility capture entrypoint; original legacy notebooks are never modified."""
import argparse
import json
from pathlib import Path
import sys
import sqlite3
from idea_space import database, default_root, capture


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=default_root())
    p.add_argument('--init-only', action='store_true')
    p.add_argument('--title')
    p.add_argument('--idea', '--details', default='')
    fields = ['category', 'summary', 'spark', 'why', 'audience', 'important-details',
              'open-questions', 'risks', 'first-step', 'related-project', 'source', 'captured-date']
    for field in fields:
        p.add_argument('--' + field, default='')
    args = p.parse_args()
    if not args.init_only and (not args.title or not args.idea.strip()):
        p.error('--title and --idea are required')
    try:
        with database(args.root) as db:
            if args.init_only:
                print(args.root)
                return 0
            context = '\n'.join(f'{f}: {getattr(args, f.replace("-", "_"))}' for f in fields
                                if getattr(args, f.replace('-', '_')))
            print(json.dumps(capture(db, args.title, args.idea, context), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f'idea-space: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
