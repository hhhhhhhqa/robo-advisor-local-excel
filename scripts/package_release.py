"""Build a public distribution from reviewed Git-tracked files only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path, PurePosixPath
import re
import subprocess
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LOCAL_DIRS = {'.git', '.venv', '.runtime', '.tools', 'local_data',
              '__pycache__', '.pytest_cache', 'work-preview'}
TEXT_SUFFIXES = {'.py', '.md', '.txt', '.json', '.toml', '.lock', '.sh',
                 '.ps1', '.cmd', '.command', '.bas', '.cls', '.applescript',
                 '.go', '.mod', '.sum', '.yml'}


def package(version: str, output: Path) -> Path:
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-beta\.\d+)?', version):
        raise ValueError('Use a release version such as v1.1.0')
    files = subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=ROOT).decode().split('\0')
    stamp = int(subprocess.check_output(['git', 'show', '-s', '--format=%ct'], cwd=ROOT))
    date_time = datetime.fromtimestamp(stamp, timezone.utc).timetuple()[:6]
    output.mkdir(parents=True, exist_ok=True)
    target = output / f'robo-advisor-local-excel-{version}.zip'
    with ZipFile(target, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for record in sorted(item for item in files if item):
            metadata, name = record.split('\t', 1)
            mode, _, stage = metadata.split()
            path = PurePosixPath(name)
            if stage != '0' or mode not in ('100644', '100755'):
                raise ValueError(f'Unsupported Git entry: {name}')
            if (LOCAL_DIRS.intersection(path.parts) or name in ('Portfolio.xlsm', 'Portfolio.xlsx')
                    or path.name.startswith('~$') or path.suffix in ('.parquet', '.db', '.log', '.pyc')):
                raise ValueError(f'Local/private data must not be tracked or packaged: {name}')
            data = (ROOT / name).read_bytes()
            if path.suffix in TEXT_SUFFIXES:
                text = data.decode('utf-8')
                if re.search('[\u3400-\u9fff]', text):
                    raise ValueError(f'Non-English text remains in {name}')
                # ZIP consumers need the same platform line endings as a checkout.
                normalized = text.replace('\r\n', '\n')
                data = (normalized.replace('\n', '\r\n') if path.suffix in ('.cmd', '.ps1') else normalized).encode()
            if path.suffix in ('.xlsx', '.xlsm'):
                with ZipFile(ROOT / name) as workbook:
                    for part in workbook.namelist():
                        if not part.endswith('.xml'):
                            continue
                        xml = workbook.read(part)
                        text = ''.join(ET.fromstring(xml).itertext())
                        if re.search('[\u3400-\u9fff]', text) or b'/Users/' in xml:
                            raise ValueError(f'Non-English or local-user content in {name}:{part}')
            entry = ZipInfo('robo-advisor-local-excel/' + name, date_time)
            entry.create_system = 3
            entry.external_attr = (int(mode, 8) << 16)
            entry.compress_type = ZIP_DEFLATED
            archive.writestr(entry, data)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(f'{digest}  {target.name}\n', encoding='utf-8')
    print(f'Created {target.name} ({target.stat().st_size:,} bytes)')
    print(f'SHA-256: {digest}')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package(args.version, args.output.resolve())
