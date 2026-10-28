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


def set_cell(xml: str, address: str, body: str, *, kind: str | None = None,
             style: str | None = None) -> str:
    pattern = rf'<c\b([^>]*\br="{address}"[^>]*)>(.*?)</c>|<c\b([^>]*\br="{address}"[^>]*)/>'
    match = re.search(pattern, xml)
    attributes = (match.group(1) or match.group(3)) if match else f' r="{address}"'
    attributes = re.sub(r'\s+t="[^"]*"', '', attributes)
    if style is not None:
        attributes = re.sub(r'\s+s="[^"]*"', '', attributes) + f' s="{style}"'
    if kind:
        attributes += f' t="{kind}"'
    cell = f'<c{attributes}>{body}</c>'
    if match:
        return xml[:match.start()] + cell + xml[match.end():]
    row_number = int(re.sub("[^0-9]", "", address))
    row = re.search(rf'<row\b[^>]*\br="{row_number}"[^>]*>.*?</row>', xml)
    if not row:
        following = next((r for r in re.finditer(r'<row\b[^>]*\br="(\d+)"', xml)
                          if int(r.group(1)) > row_number), None)
        position = following.start() if following else xml.index('</sheetData>')
        return xml[:position] + f'<row r="{row_number}">{cell}</row>' + xml[position:]
    position = row.end() - len('</row>')
    # Keep newly inserted cells in column order for native Excel.
    target_col = re.sub(r'\d', '', address)
    for existing in re.finditer(r'<c\b[^>]*\br="([A-Z]+)\d+"', row.group()):
        col = existing.group(1)
        if (len(col), col) > (len(target_col), target_col):
            position = row.start() + existing.start()
            break
    return xml[:position] + cell + xml[position:]


def set_text(xml: str, address: str, value: str, *, style: str | None = None) -> str:
    return set_cell(xml, address, f'<is><t>{escape(value)}</t></is>', kind="inlineStr", style=style)


def cash_layout(parts: dict[str, bytes]) -> None:
    """Patch only cells/styles; preserve native VBA, drawings and control parts."""
    xml = parts['xl/worksheets/sheet1.xml'].decode()
    styles = parts['xl/styles.xml'].decode()

    def cell_style(address: str) -> str:
        tag = re.search(rf'<c\b[^>]*\br="{address}"[^>]*>', xml)
        value = re.search(r'\bs="(\d+)"', tag.group()) if tag else None
        return value.group(1) if value else '0'

    # The input styles stay yellow when this builder is run repeatedly.
    migrated = 'Current cash' in re.search(r'<c\b[^>]*\br="A3"[^>]*>.*?</c>', xml).group()
    source_row = 19 if migrated else 4
    input_styles = [cell_style(f'B{source_row+i}') for i in range(5)]
    label_styles = [cell_style(f'A{4+i}') for i in range(5)]
    header_styles = [cell_style('A3'), cell_style('B3')]

    def append_part(tag: str, item: str) -> int:
        nonlocal styles
        section = re.search(rf'<{tag}\b[^>]*>.*?</{tag}>', styles)
        count = re.search(r'\bcount="(\d+)"', section.group())
        index = int(count.group(1))
        changed = section.group().replace(f'count="{index}"', f'count="{index+1}"', 1)
        changed = changed.replace(f'</{tag}>', item + f'</{tag}>')
        styles = styles[:section.start()] + changed + styles[section.end():]
        return index

    fill_section = re.search(r'<fills\b[^>]*>.*?</fills>', styles).group()
    fills = re.findall(r'<fill\b[^>]*>.*?</fill>', fill_section)
    fill_id = next((i for i, item in enumerate(fills) if 'FFEAF1F8' in item), None)
    if fill_id is None:
        fill_id = append_part('fills', '<fill><patternFill patternType="solid"><fgColor rgb="FFEAF1F8"/><bgColor indexed="64"/></patternFill></fill>')
    current_styles = []
    for original in input_styles:
        xfs = re.findall(r'<xf\b[^>]*(?:/>|>.*?</xf>)', re.search(r'<cellXfs\b[^>]*>.*?</cellXfs>', styles).group())
        updated = re.sub(r'\bfillId="\d+"', f'fillId="{fill_id}"', xfs[int(original)])
        current_styles.append(str(xfs.index(updated) if updated in xfs else append_part('cellXfs', updated)))

    for address, value, style in [('A3', 'Current cash', header_styles[0]), ('B3', 'Balance', header_styles[1]),
                                  ('A18', 'Initial cash', header_styles[0]), ('B18', 'Amount (edit)', header_styles[1])]:
        xml = set_text(xml, address, value, style=style)
    for i, currency in enumerate(('USD', 'JPY', 'EUR', 'AUD', 'CNY')):
        xml = set_text(xml, f'A{19+i}', currency, style=label_styles[i])
        xml = set_cell(xml, f'B{19+i}', f'<v>{10000 if i == 0 else 0}</v>', style=input_styles[i])
        formula = f'IF(ISNUMBER(I{50+i}),I{50+i},"Update required")'
        xml = set_cell(xml, f'B{4+i}', f'<f>{escape(formula)}</f>', style=current_styles[i])
    xml = set_text(xml, 'A9', 'Balances update after each trade.')
    parts['xl/worksheets/sheet1.xml'] = xml.encode()
    parts['xl/styles.xml'] = styles.encode()


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
            "H6": "", "H1": "Click Update once to download initial market data.",
            "A15": "Trade edits calculate automatically using local data.",
        }.items():
            xml = set_text(xml, address, value)
        xml = re.sub(r'<dataValidation\b[^>]*sqref="(?:E5:E6|E5|E6)"[^>]*>.*?</dataValidation>', '', xml)
        xml = re.sub(r'(<dataValidations\b[^>]*\bcount=")\d+("[^>]*>)',
                     lambda m: m.group(1) + str(len(re.findall(r'<dataValidation\b', xml))) + m.group(2), xml)
        parts["xl/worksheets/sheet1.xml"] = xml.encode()
        cash_layout(parts)
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
