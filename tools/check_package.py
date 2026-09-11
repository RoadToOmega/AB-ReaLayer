#!/usr/bin/env python3
"""Check distributable/source agreement without running REAPER."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
package = ROOT / 'Instruments/AB_ReaSampler.jsfx'
before = package.read_bytes()
release = json.loads((ROOT / 'release.json').read_text())
assert re.fullmatch(r'\d+\.\d+\.\d+', release['version']), 'Use an x.y.z release version'
assert release['author'].strip() and '\n' not in release['author']
assert release['description'].strip() and '\n' not in release['description']
assert release['changelog'] and all(isinstance(x, str) and x.strip() and '\n' not in x for x in release['changelog'])
subprocess.run([sys.executable, str(ROOT / 'src/build.py')], check=True, cwd=ROOT)
assert before == package.read_bytes(), 'Generated JSFX is stale. Run python3 src/build.py and commit Instruments/AB_ReaSampler.jsfx.'
header, body = before.decode().split('\n\n', 1)
assert f'// @version {release["version"]}' in header
assert f'// @author {release["author"]}' in header
assert body == (ROOT / 'AB_ReaSampler.jsfx').read_text()
assert f'version:{release["version"]}\n' in body
assert f'V{release["version"]}' in body
assert list((ROOT / 'Instruments').glob('*.jsfx')) == [package]
print('PASS: package metadata, single distributable and deterministic build')
print('JSFX SHA-256:', hashlib.sha256(before).hexdigest())
