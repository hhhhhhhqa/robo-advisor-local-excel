"""Add the native Excel form scrollbar after openpyxl has saved the workbook.

openpyxl discards form controls on a round trip. The small OOXML addition below is
based on a scrollbar saved by Excel for Mac, so each dashboard refresh keeps the
mouse-draggable time selector without requiring macros.
"""

from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile


REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
XDR_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
X14_NS = "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def add_time_slider(path: Path, trading_days: int) -> None:
    """Link a horizontal Excel scrollbar to Dashboard!F8 (1-based day index)."""
    if not 1 <= trading_days <= 30000:
        raise ValueError("Excel scrollbar needs 1 to 30000 trading days")

    with ZipFile(path) as source:
        names = set(source.namelist())
        if "xl/drawings/vmlDrawing1.vml" in names or "xl/ctrlProps/ctrlProp1.xml" in names:
            raise ValueError("Dashboard already has a form control drawing")

        sheet = source.read("xl/worksheets/sheet1.xml").decode("utf-8")
        if "<legacyDrawing" in sheet or "<controls" in sheet:
            raise ValueError("Dashboard already has a legacy drawing or controls")
        start = sheet.index("<worksheet")
        end = sheet.index(">", start)
        root_tag = sheet[start:end]
        for prefix, uri in (("r", DOC_REL_NS), ("xdr", XDR_NS),
                            ("x14", X14_NS), ("mc", MC_NS)):
            if f"xmlns:{prefix}=" not in root_tag:
                root_tag += f' xmlns:{prefix}="{uri}"'
        sheet = sheet[:start] + root_tag + sheet[end:]

        relations = ET.fromstring(source.read("xl/worksheets/_rels/sheet1.xml.rels"))
        ids = {int(item.attrib["Id"][3:]) for item in relations
               if item.attrib.get("Id", "").startswith("rId")
               and item.attrib["Id"][3:].isdigit()}
        vml_id = max(ids, default=0) + 1
        control_id = vml_id + 1
        ET.SubElement(relations, f"{{{REL_NS}}}Relationship", {
            "Id": f"rId{vml_id}",
            "Type": f"{DOC_REL_NS}/vmlDrawing",
            "Target": "../drawings/vmlDrawing1.vml",
        })
        ET.SubElement(relations, f"{{{REL_NS}}}Relationship", {
            "Id": f"rId{control_id}",
            "Type": f"{DOC_REL_NS}/ctrlProp",
            "Target": "../ctrlProps/ctrlProp1.xml",
        })

        control = (
            f'<legacyDrawing r:id="rId{vml_id}"/>'
            '<mc:AlternateContent><mc:Choice Requires="x14"><controls>'
            '<mc:AlternateContent><mc:Choice Requires="x14">'
            f'<control shapeId="1025" r:id="rId{control_id}" name="Time Slider">'
            '<controlPr defaultSize="0" autoPict="0"><anchor moveWithCells="1">'
            '<from><xdr:col>7</xdr:col><xdr:colOff>12700</xdr:colOff>'
            '<xdr:row>5</xdr:row><xdr:rowOff>12700</xdr:rowOff></from>'
            '<to><xdr:col>11</xdr:col><xdr:colOff>520700</xdr:colOff>'
            '<xdr:row>6</xdr:row><xdr:rowOff>63500</xdr:rowOff></to>'
            '</anchor></controlPr></control></mc:Choice></mc:AlternateContent>'
            '</controls></mc:Choice></mc:AlternateContent>'
        )
        sheet = sheet.replace("</worksheet>", control + "</worksheet>")
        ET.fromstring(sheet)  # Check namespace binding and well-formedness.

        types = ET.fromstring(source.read("[Content_Types].xml"))
        if not any(item.attrib.get("Extension") == "vml" for item in types):
            ET.SubElement(types, f"{{{CT_NS}}}Default", {
                "Extension": "vml",
                "ContentType": "application/vnd.openxmlformats-officedocument.vmlDrawing",
            })
        ET.SubElement(types, f"{{{CT_NS}}}Override", {
            "PartName": "/xl/ctrlProps/ctrlProp1.xml",
            "ContentType": "application/vnd.ms-excel.controlproperties+xml",
        })

        ctrl_prop = (
            f'<formControlPr xmlns="{X14_NS}" objectType="Scroll" dx="15" '
            f'fmlaLink="$F$8" horiz="1" max="{trading_days}" min="1" '
            f'page="5" val="{trading_days}"/>'
        )
        vml = (
            '<xml xmlns:v="urn:schemas-microsoft-com:vml" '
            'xmlns:o="urn:schemas-microsoft-com:office:office" '
            'xmlns:x="urn:schemas-microsoft-com:office:excel">'
            '<o:shapelayout v:ext="edit"><o:idmap v:ext="edit" data="1"/>'
            '</o:shapelayout><v:shapetype id="_x0000_t201" coordsize="21600,21600" '
            'o:spt="201" path="m,l,21600r21600,l21600,xe"><v:stroke joinstyle="miter"/>'
            '<v:path shadowok="f" o:extrusionok="f" strokeok="f" fillok="f" '
            'o:connecttype="rect"/><o:lock v:ext="edit" shapetype="t"/>'
            '</v:shapetype><v:shape id="_x0000_s1025" type="#_x0000_t201" '
            'style="position:absolute;margin-left:655pt;margin-top:77pt;width:490pt;'
            'height:18pt;z-index:1" o:insetmode="auto">'
            '<o:lock v:ext="edit" rotation="t" text="t"/>'
            '<x:ClientData ObjectType="Scroll"><x:SizeWithCells/>'
            '<x:Anchor>7, 1, 5, 1, 11, 41, 6, 5</x:Anchor>'
            '<x:FmlaLink>$F$8</x:FmlaLink>'
            f'<x:Val>{trading_days}</x:Val><x:Min>1</x:Min>'
            f'<x:Max>{trading_days}</x:Max><x:Inc>1</x:Inc>'
            '<x:Page>5</x:Page><x:Horiz/><x:Dx>15</x:Dx>'
            '</x:ClientData></v:shape></xml>'
        )

        replacements = {
            "[Content_Types].xml": ET.tostring(types, encoding="utf-8", xml_declaration=True),
            "xl/worksheets/sheet1.xml": sheet.encode("utf-8"),
            "xl/worksheets/_rels/sheet1.xml.rels": ET.tostring(
                relations, encoding="utf-8", xml_declaration=True),
        }
        temp = path.with_name(path.stem + ".controls.xlsx")
        with ZipFile(temp, "w") as output:
            for item in source.infolist():
                output.writestr(item, replacements.get(item.filename, source.read(item.filename)))
            output.writestr("xl/ctrlProps/ctrlProp1.xml", ctrl_prop)
            output.writestr("xl/drawings/vmlDrawing1.vml", vml)
    os.replace(temp, path)
