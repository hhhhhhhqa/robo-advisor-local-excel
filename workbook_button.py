"""Attach the native Excel-authored macro project without changing cell data."""
from pathlib import Path
import re
import shutil
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

TEMPLATE_NAME = "robo_advisor_dashboard_button.xlsm"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def template_path(root: Path) -> Path:
    return root / "examples" / "excel" / TEMPLATE_NAME


def attach_project(source: Path, target: Path, root: Path) -> None:
    """Keep all source parts; add a known native VBA project and its metadata."""
    with ZipFile(template_path(root)) as template:
        project = template.read("xl/vbaProject.bin")
    with ZipFile(source) as incoming, ZipFile(target, "w", ZIP_DEFLATED) as outgoing:
        replacements = {}
        types = ET.fromstring(incoming.read("[Content_Types].xml"))
        for item in types:
            if item.attrib.get("PartName") == "/xl/workbook.xml":
                item.set("ContentType", "application/vnd.ms-excel.sheet.macroEnabled.main+xml")
        if not any(item.attrib.get("PartName") == "/xl/vbaProject.bin" for item in types):
            ET.SubElement(types, f"{{{CT_NS}}}Override", {
                "PartName": "/xl/vbaProject.bin", "ContentType": "application/vnd.ms-office.vbaProject"})
        replacements["[Content_Types].xml"] = ET.tostring(types, encoding="utf-8", xml_declaration=True)
        relations = ET.fromstring(incoming.read("xl/_rels/workbook.xml.rels"))
        if not any(item.attrib.get("Type", "").endswith("/vbaProject") for item in relations):
            used = {item.attrib["Id"] for item in relations}
            index = 1
            while f"rId{index}" in used:
                index += 1
            ET.SubElement(relations, f"{{{REL_NS}}}Relationship", {
                "Id": f"rId{index}", "Target": "vbaProject.bin",
                "Type": "http://schemas.microsoft.com/office/2006/relationships/vbaProject"})
        replacements["xl/_rels/workbook.xml.rels"] = ET.tostring(relations, encoding="utf-8", xml_declaration=True)
        # Patch these small tags as text to retain Office's namespace declarations.
        for part, tag, name in (("xl/workbook.xml", "workbookPr", "ThisWorkbook"),
                                ("xl/worksheets/sheet1.xml", "sheetPr", "Sheet1")):
            text = incoming.read(part).decode("utf-8")
            pattern = rf"<{tag}\b[^>]*>"
            match = re.search(pattern, text)
            if match:
                old = match.group()
                clean = re.sub(r'\s+codeName="[^"]*"', "", old)
                position = clean.rfind("/>") if clean.endswith("/>") else clean.rfind(">")
                new = clean[:position] + f' codeName="{name}"' + clean[position:]
                text = text[:match.start()] + new + text[match.end():]
            else:
                root_end = text.index(">", text.index("<worksheet" if tag == "sheetPr" else "<workbook")) + 1
                text = text[:root_end] + f'<{tag} codeName="{name}"/>' + text[root_end:]
            replacements[part] = text.encode("utf-8")
        for item in incoming.infolist():
            if item.filename != "xl/vbaProject.bin":
                outgoing.writestr(item, replacements.get(item.filename, incoming.read(item.filename)))
        outgoing.writestr("xl/vbaProject.bin", project)


def prepare_button_workbook(root: Path) -> Path:
    target = root / "Portfolio.xlsm"
    if not target.exists():
        legacy = root / "Portfolio.xlsx"
        if legacy.exists():
            staged = root / "local_data" / "upgrade.xlsm"
            staged.parent.mkdir(exist_ok=True)
            attach_project(legacy, staged, root)
            staged.replace(target)
            print("已将旧 Excel 的资金和交易复制到 Portfolio.xlsm；原 Portfolio.xlsx 已保留。")
        else:
            shutil.copy2(template_path(root), target)
            print("已创建带更新按钮的 Portfolio.xlsm（初始现金 10,000 USD）。")
    return target


def install_mac_helper(root: Path) -> None:
    if sys.platform == "darwin":
        helper = "RoboAdvisorExcel_v2.applescript"
        directory = Path.home() / "Library" / "Application Scripts" / "com.microsoft.Excel"
        directory.mkdir(parents=True, exist_ok=True)
        source = root / "excel_button" / helper
        target = directory / helper
        if not target.exists() or target.read_bytes() != source.read_bytes():
            shutil.copy2(source, target)
