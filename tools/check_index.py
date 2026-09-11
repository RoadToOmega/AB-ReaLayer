#!/usr/bin/env python3
"""Validate the generated catalogue before the workflow commits it."""
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
index = ET.parse(ROOT / 'index.xml').getroot()
assert index.tag == 'index' and index.attrib['version'] == '1'
assert index.attrib['name'] == 'AB ReaLayer'
categories = index.findall('category')
assert len(categories) == 1 and categories[0].attrib['name'] == 'Instruments'
packages = categories[0].findall('reapack')
assert len(packages) == 1
package = packages[0]
assert package.attrib['name'] == 'VariationSampler-M11.jsfx'
assert package.attrib['type'] == 'effect'
version = json.loads((ROOT / 'release.json').read_text())['version']
versions = package.findall('version')
assert len({x.attrib['name'] for x in versions}) == len(versions)
assert any(x.attrib['name'] == version for x in versions), 'Current release missing from index'
repository = os.environ.get('GITHUB_REPOSITORY')
for item in versions:
    sources = item.findall('source')
    assert len(sources) == 1, 'Each version must install only the self-contained JSFX'
    url = (sources[0].text or '').strip()
    match = re.fullmatch(r'https://raw\.githubusercontent\.com/([^/]+/[^/]+)/([0-9a-f]{40})/Instruments/VariationSampler-M11\.jsfx', url)
    assert match, f'Expected immutable commit download URL: {url}'
    if repository:
        assert match[1] == repository, 'Download points outside this repository'
    if item.attrib['name'] == version:
        published = subprocess.check_output(['git', 'show', match[2] + ':Instruments/VariationSampler-M11.jsfx'], cwd=ROOT)
        assert published == (ROOT / 'Instruments/VariationSampler-M11.jsfx').read_bytes(), 'Changed bytes under an existing version. Bump release.json and rebuild.'
    assert sources[0].get('file') in (None, 'VariationSampler-M11.jsfx'), 'Unexpected install destination'
print('PASS: one JSFX package, current release and immutable download URLs')
