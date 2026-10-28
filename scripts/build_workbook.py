"""Developer-only VBA rebuild without launching Excel or rewriting OOXML parts.

Requires Go and the pinned scripts/vba-builder module. Runtime users need neither.
"""
from pathlib import Path
from html import escape
import re
import subprocess
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "examples/excel/robo_advisor_dashboard_button.xlsm"


def set_text(xml: str, address: str, value: str) -> str:
    pattern = rf'<c\b([^>]*\br="{address}"[^>]*)>(.*?)</c>|<c\b([^>]*\br="{address}"[^>]*)/>'
    match = re.search(pattern, xml)
    attributes = (match.group(1) or match.group(3)) if match else f' r="{address}"'
    attributes = re.sub(r'\s+t="[^"]*"', '', attributes)
    cell = f'<c{attributes} t="inlineStr"><is><t>{escape(value)}</t></is></c>'
    if match:
        return xml[:match.start()] + cell + xml[match.end():]
    row = re.search(rf'<row\b[^>]*\br="{re.sub("[^0-9]", "", address)}"[^>]*>.*?</row>', xml)
    if not row:
        raise ValueError(f"Missing template row for {address}")
    position = row.end() - len('</row>')
    return xml[:position] + cell + xml[position:]


def build() -> None:
    with tempfile.TemporaryDirectory() as staging:
        directory = Path(staging)
        incoming, outgoing = directory / "input.bin", directory / "output.bin"
        with ZipFile(TEMPLATE) as source:
            incoming.write_bytes(source.read("xl/vbaProject.bin"))
            parts = {name: source.read(name) for name in source.namelist()}
        subprocess.run(["go", "run", ".", str(incoming), str(ROOT / "excel_button"), str(outgoing)],
                       cwd=ROOT / "scripts/vba-builder", check=True)
        parts["xl/vbaProject.bin"] = outgoing.read_bytes()
        xml = parts["xl/worksheets/sheet1.xml"].decode()
        for address, value in {
            "D5": "Market data", "E5": "Manual Update", "D6": "Calculations", "E6": "Automatic (local)",
            "H5": "Click Update to download prices and FX rates.",
            "H6": "Click Update once to download initial market data.",
            "A15": "Trade edits calculate automatically using local data.",
        }.items():
            xml = set_text(xml, address, value)
        xml = re.sub(r'<dataValidation\b[^>]*sqref="(?:E5:E6|E5|E6)"[^>]*>.*?</dataValidation>', '', xml)
        xml = re.sub(r'(<dataValidations\b[^>]*\bcount=")\d+("[^>]*>)',
                     lambda m: m.group(1) + str(len(re.findall(r'<dataValidation\b', xml))) + m.group(2), xml)
        parts["xl/worksheets/sheet1.xml"] = xml.encode()
        for name in parts:
            if name.startswith("xl/drawings/") and name.endswith(".xml"):
                parts[name] = parts[name].replace(b"Update results", b"Update")
        target = directory / "template.xlsm"
        with ZipFile(target, "w", ZIP_DEFLATED) as archive:
            for name, data in parts.items():
                archive.writestr(name, data)
        TEMPLATE.write_bytes(target.read_bytes())


if __name__ == "__main__":
    build()
