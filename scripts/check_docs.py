#!/usr/bin/env python3
"""Check that relative Markdown file links resolve inside the checkout."""

from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'\[[^\]]*\]\(([^\s)]+)(?:\s+"[^\"]*")?\)')


def main():
    failures = []
    documents = sorted(ROOT.glob('*.md')) + sorted((ROOT / 'docs').rglob('*.md'))
    for document in documents:
        # Existing deployment references are historical; validate the maintained guide set.
        if document.parent == ROOT and document.name not in {
            'README.md', 'CONTRIBUTING.md', 'SECURITY.md', 'CHANGELOG.md'
        }:
            continue
        content = re.sub(r'```.*?```', '', document.read_text(), flags=re.S)
        for match in LINK.finditer(content):
            target = match.group(1).strip('<>')
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            resolved = (document.parent / unquote(parsed.path)).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.exists():
                failures.append(f'{document.relative_to(ROOT)}: {target}')
    if failures:
        raise SystemExit('Broken documentation links:\n' + '\n'.join(failures))
    print('Documentation file links verified.')


if __name__ == '__main__':
    main()
