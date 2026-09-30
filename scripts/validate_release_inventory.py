"""Validate the release inventory against Git blobs and Git LFS object IDs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = 'PUBLIC_REPO_FILE_LIST_SHA256.csv'


def records():
    entries = subprocess.check_output(['git', 'ls-files', '-s', '-z'], cwd=ROOT)
    objects = {}
    for entry in entries.decode('utf-8').split('\0'):
        if not entry:
            continue
        meta, path = entry.split('\t', 1)
        mode, oid, stage = meta.split()
        if stage != '0':
            raise ValueError('Resolve index conflicts before checking the inventory')
        if path != INVENTORY:
            objects[path] = oid
    process = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    cache = {}
    try:
        for path, oid in sorted(objects.items()):
            if oid not in cache:
                process.stdin.write((oid + '\n').encode('ascii'))
                process.stdin.flush()
                header = process.stdout.readline().decode('ascii').split()
                size = int(header[2])
                data = process.stdout.read(size)
                if process.stdout.read(1) != b'\n':
                    raise ValueError('Invalid git cat-file response')
                if data.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
                    fields = dict(line.split(' ', 1) for line in data.decode('ascii').splitlines())
                    cache[oid] = (int(fields['size']), fields['oid'].split(':')[1])
                else:
                    cache[oid] = (size, hashlib.sha256(data).hexdigest())
            size, sha = cache[oid]
            yield {'relative_path': path, 'bytes': str(size), 'sha256': sha}
    finally:
        process.stdin.close()
        process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Regenerate from staged content after git add')
    args = parser.parse_args()
    actual = list(records())
    path = ROOT / INVENTORY
    if args.write:
        with path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, ['relative_path', 'bytes', 'sha256'],
                                    quoting=csv.QUOTE_ALL, lineterminator='\n')
            writer.writeheader()
            writer.writerows(actual)
    else:
        with path.open(encoding='utf-8', newline='') as handle:
            expected = list(csv.DictReader(handle))
        if expected != actual:
            raise ValueError('Inventory does not match the Git index; compare staged changes and release version')
    print(json.dumps({'files': len(actual), 'basis': 'Git blob bytes or LFS payload object IDs',
                      'action': 'written' if args.write else 'validated'}))


if __name__ == '__main__':
    main()
