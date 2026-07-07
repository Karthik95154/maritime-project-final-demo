import json
import os
import tempfile
from datetime import datetime
from urllib.parse import urlparse

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

import requests


class DocumentGenerationModule:
    LABOR_KEYWORDS = ("labor", "welding", "blasting", "grinding", "inspection")
    EQUIPMENT_KEYWORDS = ("scaffolding", "machine", "equipment", "rental", "crane", "compressor")

    def __init__(
        self,
        gemini_model_name="gemini-1.5-flash",
        output_folder="outputs/final_reports"
    ):
        self.gemini_model_name = gemini_model_name
        self.output_folder = output_folder
        os.makedirs(self.output_folder, exist_ok=True)

    def load_json(self, path):
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _format_currency(self, value, currency):
        return f"{self._safe_float(value):,.2f} {currency}"

    def _clean_label(self, value, fallback):
        if not value:
            return fallback
        return str(value).replace("_", " ").strip().title()

    def _compact_text(self, value, fallback):
        if not value:
            return fallback
        text = " ".join(str(value).split())
        return text[:180].rstrip() if len(text) > 180 else text

    def _categorize_item(self, item_name):
        normalized = str(item_name or "").lower()
        if any(keyword in normalized for keyword in self.LABOR_KEYWORDS):
            return "labor"
        if any(keyword in normalized for keyword in self.EQUIPMENT_KEYWORDS):
            return "equipment"
        return "material"

    def _normalize_item(self, item, default_currency):
        quantity_per_sqm = self._safe_float(item.get("quantity_per_sqm", 0))
        required_quantity = self._safe_float(
            item.get("required_quantity", item.get("quantity", quantity_per_sqm))
        )
        unit_cost = self._safe_float(item.get("unit_cost", item.get("cost", 0)))
        total_cost = required_quantity * unit_cost
        return {
            "item_name": item.get("item_name") or item.get("name") or "New Item",
            "metrics": item.get("metrics") or item.get("unit") or "pcs",
            "quantity_per_sqm": quantity_per_sqm,
            "required_quantity": required_quantity,
            "unit_cost": unit_cost,
            "currency": item.get("currency") or default_currency,
            "total_cost": total_cost,
        }

    def _normalize_report_payload(self, repair_outputs):
        source = repair_outputs if isinstance(repair_outputs, dict) else {}
        repair_summary = source.get("repair_summary") if isinstance(source.get("repair_summary"), dict) else {}
        defect_repairs = source.get("defect_repairs") if isinstance(source.get("defect_repairs"), dict) else {}
        default_currency = repair_summary.get("currency", "INR")

        normalized_repairs = {}
        total_estimated_cost = 0.0
        total_material_cost = 0.0
        total_labor_cost = 0.0
        total_equipment_cost = 0.0
        severity_distribution = {"low": 0, "medium": 0, "high": 0}

        for defect_id, defect_data in defect_repairs.items():
            estimation = defect_data.get("repair_estimation", {})
            defect_currency = estimation.get("currency", default_currency)
            raw_items = estimation.get("required_items", [])
            required_items = [
                self._normalize_item(item, defect_currency)
                for item in raw_items
                if isinstance(item, dict)
            ]

            defect_total = 0.0
            defect_material = 0.0
            defect_labor = 0.0
            defect_equipment = 0.0

            for item in required_items:
                category = self._categorize_item(item.get("item_name"))
                line_total = self._safe_float(item.get("total_cost"))
                defect_total += line_total
                if category == "labor":
                    defect_labor += line_total
                elif category == "equipment":
                    defect_equipment += line_total
                else:
                    defect_material += line_total

            if not required_items:
                defect_total = self._safe_float(estimation.get("estimated_total_cost", 0))
                defect_material = self._safe_float(estimation.get("material_cost", 0))
                defect_labor = self._safe_float(estimation.get("labor_cost", 0))
                defect_equipment = self._safe_float(estimation.get("equipment_cost", 0))

            severity = str(defect_data.get("severity", "low")).lower()
            severity_distribution[severity] = severity_distribution.get(severity, 0) + 1

            normalized_repairs[defect_id] = {
                **defect_data,
                "repair_estimation": {
                    **estimation,
                    "currency": defect_currency,
                    "required_items": required_items,
                    "estimated_total_cost": round(defect_total, 2),
                    "material_cost": round(defect_material, 2),
                    "labor_cost": round(defect_labor, 2),
                    "equipment_cost": round(defect_equipment, 2),
                },
            }

            total_estimated_cost += defect_total
            total_material_cost += defect_material
            total_labor_cost += defect_labor
            total_equipment_cost += defect_equipment

        return {
            **source,
            "repair_summary": {
                **repair_summary,
                "total_defects": len(normalized_repairs),
                "total_estimated_cost": round(total_estimated_cost, 2),
                "total_material_cost": round(total_material_cost, 2),
                "total_labor_cost": round(total_labor_cost, 2),
                "total_equipment_cost": round(total_equipment_cost, 2),
                "currency": default_currency,
                "severity_distribution": severity_distribution,
            },
            "defect_repairs": normalized_repairs,
        }

    def _set_cell_shading(self, cell, fill):
        tc_pr = cell._tc.get_or_add_tcPr()
        shading = OxmlElement("w:shd")
        shading.set(qn("w:fill"), fill)
        tc_pr.append(shading)

    def _set_table_borders(self, table, color="9FA8B2"):
        tbl = table._tbl
        tbl_pr = tbl.tblPr
        borders = tbl_pr.first_child_found_in("w:tblBorders")
        if borders is None:
            borders = OxmlElement("w:tblBorders")
            tbl_pr.append(borders)

        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            tag = f"w:{edge}"
            element = borders.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                borders.append(element)
            element.set(qn("w:val"), "single")
            element.set(qn("w:sz"), "6")
            element.set(qn("w:space"), "0")
            element.set(qn("w:color"), color)

    def _style_table(self, table):
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = "Table Grid"
        self._set_table_borders(table)
        for row in table.rows:
            for cell in row.cells:
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.space_before = Pt(0)
                    paragraph.paragraph_format.space_after = Pt(0)
                    for run in paragraph.runs:
                        run.font.size = Pt(9)

    def _configure_document(self, document):
        section = document.sections[0]
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.55)
        section.left_margin = Inches(0.55)
        section.right_margin = Inches(0.55)

        styles = document.styles
        styles["Normal"].font.name = "Calibri"
        styles["Normal"].font.size = Pt(9)
        styles["Normal"].paragraph_format.space_after = Pt(3)

    def _add_header(self, document, title_text, reference_code, estimate_date):
        table = document.add_table(rows=1, cols=2)
        table.autofit = False
        table.columns[0].width = Inches(4.8)
        table.columns[1].width = Inches(2.2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        left_cell = table.rows[0].cells[0]
        right_cell = table.rows[0].cells[1]

        brand = left_cell.paragraphs[0]
        brand.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = brand.add_run("Marine Technical Services")
        run.bold = True
        run.font.size = Pt(14)
        run.font.color.rgb = RGBColor(31, 54, 91)

        for line in (
            "Hull inspection and repair estimation support",
            "Prepared from digital survey findings",
            "Contact: operations@marine-technical.local"
        ):
            paragraph = left_cell.add_paragraph(line)
            paragraph.paragraph_format.space_after = Pt(1)

        self._set_cell_shading(right_cell, "E9EFF7")
        title = right_cell.paragraphs[0]
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title.add_run(title_text)
        title_run.bold = True
        title_run.font.size = Pt(14)

        ref_paragraph = right_cell.add_paragraph()
        ref_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ref_run = ref_paragraph.add_run(f"Ref: {reference_code}")
        ref_run.bold = True

        date_paragraph = right_cell.add_paragraph()
        date_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        date_paragraph.add_run(f"Date: {estimate_date}")

        self._style_table(table)
        document.add_paragraph()

    def _add_metadata(self, document, vessel_name, imo_number, report_scope, currency):
        table = document.add_table(rows=2, cols=4)
        labels = [
            ("Vessel Name", vessel_name or "To be confirmed"),
            ("IMO Number", imo_number or "To be confirmed"),
            ("Document Type", "Repair Cost Estimate"),
            ("Scope", report_scope),
            ("Prepared By", "Automated Inspection Workflow"),
            ("Currency", currency),
            ("Basis", "Inspection findings and repair rules"),
            ("Validity", "Subject to onboard verification"),
        ]

        label_fill = "DCE6F1"
        index = 0
        for row in table.rows:
            for _ in range(2):
                label_cell = row.cells[index]
                value_cell = row.cells[index + 1]
                title, value = labels.pop(0)
                label_cell.text = title
                value_cell.text = value
                self._set_cell_shading(label_cell, label_fill)
                for paragraph in label_cell.paragraphs:
                    for run in paragraph.runs:
                        run.bold = True
                index += 2
            index = 0

        self._style_table(table)
        document.add_paragraph()

    def _build_scope_rows(self, defect_repairs):
        rows = []
        for number, (defect_id, repair_data) in enumerate(defect_repairs.items(), start=1):
            metadata = repair_data.get("defect_metadata", {})
            estimation = repair_data.get("repair_estimation", {})
            defect_name = self._clean_label(repair_data.get("defect_name"), "General Defect")
            severity = self._clean_label(repair_data.get("severity"), "Low")
            area = self._safe_float(metadata.get("defect_area"))
            location = " / ".join(
                part.get("part_name", "").replace("_", " ").title()
                for part in metadata.get("overlapping_parts", [])
                if part.get("part_name")
            ) or "General area"
            process = self._compact_text(repair_data.get("repair_process"), "Repair procedure to be confirmed.")
            required_items = estimation.get("required_items", [])

            if required_items:
                defect_total = max(self._safe_float(estimation.get("estimated_total_cost")), 0.0)
                defect_material = max(self._safe_float(estimation.get("material_cost")), 0.0)
                defect_service = max(
                    self._safe_float(estimation.get("labor_cost")) +
                    self._safe_float(estimation.get("equipment_cost")),
                    0.0,
                )
                for item_index, item in enumerate(required_items, start=1):
                    item_name = self._clean_label(item.get("item_name"), "Repair Item")
                    quantity = self._safe_float(item.get("required_quantity"))
                    metrics = item.get("metrics") or "unit"
                    item_total = max(self._safe_float(item.get("total_cost")), 0.0)
                    category = self._categorize_item(item_name)
                    if category == "material":
                        material_share = item_total
                        service_cost = 0.0
                    else:
                        material_share = 0.0
                        service_cost = item_total
                    description = (
                        f"{defect_name} at {location}. {process} "
                        f"Item: {item_name} ({quantity:.2f} {metrics})."
                    )
                    rows.append({
                        "no": number if item_index == 1 else "",
                        "description": description,
                        "service": service_cost,
                        "material": material_share,
                        "total": item_total if item_total > 0 else service_cost + material_share,
                        "severity": severity,
                        "area": area,
                        "defect_id": defect_id,
                    })
            else:
                base_total = self._safe_float(estimation.get("estimated_total_cost"))
                material_cost = self._safe_float(estimation.get("material_cost"))
                service_cost = max(base_total - material_cost, 0.0)
                rows.append({
                    "no": number,
                    "description": f"{defect_name} at {location}. {process}",
                    "service": service_cost,
                    "material": material_cost,
                    "total": base_total,
                    "severity": severity,
                    "area": area,
                    "defect_id": defect_id,
                })

        return rows

    def _add_summary_band(self, document, repair_summary):
        currency = repair_summary.get("currency", "INR")
        severity = repair_summary.get("severity_distribution", {})
        severity_text = (
            f"Low: {severity.get('low', 0)} | "
            f"Medium: {severity.get('medium', 0)} | "
            f"High: {severity.get('high', 0)}"
        )

        table = document.add_table(rows=2, cols=4)
        content = [
            ("Total Defects", str(repair_summary.get("total_defects", 0))),
            ("Estimated Total", self._format_currency(repair_summary.get("total_estimated_cost", 0), currency)),
            ("Material Cost", self._format_currency(repair_summary.get("total_material_cost", 0), currency)),
            ("Labor + Equipment", self._format_currency(
                self._safe_float(repair_summary.get("total_labor_cost", 0)) +
                self._safe_float(repair_summary.get("total_equipment_cost", 0)),
                currency,
            )),
            ("Severity Mix", severity_text),
            ("Issue Count", str(repair_summary.get("total_defects", 0))),
            ("Basis of Estimate", "AI review and operator-approved quantities"),
            ("Status", "Budgetary estimate"),
        ]

        cursor = 0
        for row in table.rows:
            for pair_index in range(0, 4, 2):
                label_cell = row.cells[pair_index]
                value_cell = row.cells[pair_index + 1]
                label, value = content[cursor]
                label_cell.text = label
                value_cell.text = value
                self._set_cell_shading(label_cell, "D9EAD3")
                for paragraph in label_cell.paragraphs:
                    for run in paragraph.runs:
                        run.bold = True
                cursor += 1

        self._style_table(table)
        document.add_paragraph()

    def _add_scope_table(self, document, defect_repairs, currency):
        heading = document.add_paragraph()
        heading_run = heading.add_run("WORK SCOPE AND COST BREAKDOWN")
        heading_run.bold = True
        heading_run.font.size = Pt(11)

        table = document.add_table(rows=1, cols=5)
        headers = table.rows[0].cells
        headers[0].text = "No."
        headers[1].text = "Work Description"
        headers[2].text = "Service"
        headers[3].text = "Material"
        headers[4].text = "Total"

        for cell in headers:
            self._set_cell_shading(cell, "B4C6E7")
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = True

        grand_service = 0.0
        grand_material = 0.0
        grand_total = 0.0

        for row_data in self._build_scope_rows(defect_repairs):
            row = table.add_row().cells
            row[0].text = str(row_data["no"])
            row[1].text = row_data["description"]
            row[2].text = self._format_currency(row_data["service"], currency)
            row[3].text = self._format_currency(row_data["material"], currency)
            row[4].text = self._format_currency(row_data["total"], currency)
            grand_service += row_data["service"]
            grand_material += row_data["material"]
            grand_total += row_data["total"]

        total_row = table.add_row().cells
        total_row[0].merge(total_row[1])
        total_row[0].text = "TOTAL ESTIMATED COST"
        total_row[2].text = self._format_currency(grand_service, currency)
        total_row[3].text = self._format_currency(grand_material, currency)
        total_row[4].text = self._format_currency(grand_total, currency)

        for cell in total_row:
            self._set_cell_shading(cell, "FCE5CD")
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = True

        self._style_table(table)
        document.add_paragraph()

    def _add_defect_register(self, document, defect_repairs):
        heading = document.add_paragraph()
        heading_run = heading.add_run("DEFECT REGISTER")
        heading_run.bold = True
        heading_run.font.size = Pt(11)

        table = document.add_table(rows=1, cols=5)
        headers = table.rows[0].cells
        headers[0].text = "Defect ID"
        headers[1].text = "Defect Type"
        headers[2].text = "Location"
        headers[3].text = "Severity"
        headers[4].text = "Area"

        for cell in headers:
            self._set_cell_shading(cell, "D9D2E9")
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = True

        for defect_id, repair_data in defect_repairs.items():
            metadata = repair_data.get("defect_metadata", {})
            parts = metadata.get("overlapping_parts", [])
            location = " / ".join(
                part.get("part_name", "").replace("_", " ").title()
                for part in parts
                if part.get("part_name")
            ) or "General area"
            row = table.add_row().cells
            row[0].text = str(defect_id)
            row[1].text = self._clean_label(repair_data.get("defect_name"), "General Defect")
            row[2].text = location
            row[3].text = self._clean_label(repair_data.get("severity"), "Low")
            row[4].text = f"{self._safe_float(metadata.get('defect_area')):.2f} {metadata.get('area_metrics') or 'sqm'}"

        self._style_table(table)
        document.add_paragraph()

    def _add_defect_proof_section(self, document, defect_repairs):
        heading = document.add_paragraph()
        heading_run = heading.add_run("DEFECT PROOF AND COST JUSTIFICATION")
        heading_run.bold = True
        heading_run.font.size = Pt(11)

        for defect_id, repair_data in defect_repairs.items():
            metadata = repair_data.get("defect_metadata", {})
            estimation = repair_data.get("repair_estimation", {})
            parts = metadata.get("overlapping_parts", [])
            location = " / ".join(
                part.get("part_name", "").replace("_", " ").title()
                for part in parts
                if part.get("part_name")
            ) or "General area"

            title = document.add_paragraph()
            title_run = title.add_run(
                f"{defect_id} - {self._clean_label(repair_data.get('defect_name'), 'General Defect')}"
            )
            title_run.bold = True

            details = document.add_paragraph()
            details.add_run("Location: ").bold = True
            details.add_run(location)
            details.add_run("   Severity: ").bold = True
            details.add_run(self._clean_label(repair_data.get("severity"), "Low"))
            details.add_run("   Approved Total: ").bold = True
            details.add_run(
                self._format_currency(
                    estimation.get("estimated_total_cost", 0),
                    estimation.get("currency", "INR"),
                )
            )

            reason = document.add_paragraph()
            reason.add_run("Basis: ").bold = True
            reason.add_run(self._compact_text(
                repair_data.get("repair_process") or repair_data.get("description"),
                "Line items are based on the approved defect repair scope.",
            ))

            image_path = metadata.get("best_frame_path")
            temp_image_path = None
            if image_path:
                try:
                    parsed = urlparse(str(image_path))
                    if parsed.scheme in ("http", "https"):
                        response = requests.get(str(image_path), timeout=15)
                        response.raise_for_status()
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                            temp_file.write(response.content)
                            temp_image_path = temp_file.name
                        document.add_picture(temp_image_path, width=Inches(5.4))
                    elif os.path.exists(image_path):
                        document.add_picture(image_path, width=Inches(5.4))
                except Exception as exc:
                    fallback = document.add_paragraph()
                    fallback.add_run("Image note: ").bold = True
                    fallback.add_run(f"Proof image could not be embedded ({exc}).")
                finally:
                    if temp_image_path and os.path.exists(temp_image_path):
                        os.unlink(temp_image_path)

            proof_table = document.add_table(rows=1, cols=4)
            proof_headers = proof_table.rows[0].cells
            proof_headers[0].text = "Approved Item"
            proof_headers[1].text = "Qty"
            proof_headers[2].text = "Unit Cost"
            proof_headers[3].text = "Line Total"
            for cell in proof_headers:
                self._set_cell_shading(cell, "F4CCCC")
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.bold = True

            for item in estimation.get("required_items", []):
                row = proof_table.add_row().cells
                row[0].text = self._clean_label(item.get("item_name"), "Repair Item")
                row[1].text = f"{self._safe_float(item.get('required_quantity')):.2f} {item.get('metrics') or 'pcs'}"
                row[2].text = self._format_currency(item.get("unit_cost", 0), item.get("currency", "INR"))
                row[3].text = self._format_currency(item.get("total_cost", 0), item.get("currency", "INR"))

            self._style_table(proof_table)
            document.add_paragraph()

    def _add_notes(self, document):
        heading = document.add_paragraph()
        run = heading.add_run("NOTES")
        run.bold = True
        run.font.size = Pt(11)

        notes = [
            "This document is a clean estimate template generated from inspection findings.",
            "All quantities and locations should be confirmed onboard before commercial issue.",
            "The format intentionally avoids real client identities, billing data, and company names.",
            "Descriptions are kept brief for operational review and approval workflows.",
        ]

        for note in notes:
            paragraph = document.add_paragraph(style="List Bullet")
            paragraph.add_run(note)

    def _build_document(self, title_text, reference_code, vessel_name, repair_summary, defect_repairs):
        document = Document()
        self._configure_document(document)
        estimate_date = datetime.now().strftime("%d-%m-%Y")
        currency = repair_summary.get("currency", "INR")

        self._add_header(document, title_text, reference_code, estimate_date)
        self._add_metadata(
            document,
            vessel_name=vessel_name,
            imo_number=repair_summary.get("imo_number"),
            report_scope="Hull defect repair estimate",
            currency=currency,
        )
        self._add_summary_band(document, repair_summary)
        self._add_scope_table(document, defect_repairs, currency)
        self._add_defect_register(document, defect_repairs)
        self._add_defect_proof_section(document, defect_repairs)
        self._add_notes(document)
        return document

    def _finalize_output(self, output_docx_path):
        from services.supabase_service import supabase_service

        if supabase_service.is_configured():
            try:
                public_url = supabase_service.upload_file(
                    output_docx_path,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                return {
                    "document_docx_url": public_url,
                    "document_pdf_url": public_url,
                }
            except Exception as exc:
                print(f"Failed to upload report to Supabase: {exc}")

        return {
            "document_docx_url": output_docx_path,
            "document_pdf_url": output_docx_path,
        }

    def create_report(self, repair_estimation_json_path):
        repair_outputs = self._normalize_report_payload(self.load_json(repair_estimation_json_path))
        repair_summary = repair_outputs.get("repair_summary", {})
        defect_repairs = repair_outputs.get("defect_repairs", {})
        document = self._build_document(
            title_text="REPAIR ESTIMATE",
            reference_code="MI-SINGLE",
            vessel_name=repair_outputs.get("vessel_name") or "Vessel Under Inspection",
            repair_summary=repair_summary,
            defect_repairs=defect_repairs,
        )

        output_docx_path = os.path.join(self.output_folder, "vessel_inspection_report.docx")
        document.save(output_docx_path)
        return self._finalize_output(output_docx_path)

    def create_batch_report(self, batch_id: str, repair_json_paths: list[str], vessel_name: str):
        repair_payloads = []
        for path in repair_json_paths:
            if not os.path.exists(path):
                continue
            repair_payloads.append(self.load_json(path))

        return self.create_batch_report_from_payloads(batch_id, repair_payloads, vessel_name)

    def create_batch_report_from_payloads(self, batch_id: str, repair_payloads: list[dict], vessel_name: str):
        aggregated_total_defects = 0
        aggregated_total_cost = 0.0
        aggregated_material_cost = 0.0
        aggregated_labor_cost = 0.0
        aggregated_equipment_cost = 0.0
        severity_distribution = {"low": 0, "medium": 0, "high": 0}
        currency = "INR"
        all_defect_repairs = {}

        for payload in repair_payloads:
            repair_outputs = self._normalize_report_payload(payload or {})
            repair_summary = repair_outputs.get("repair_summary", {})
            aggregated_total_defects += int(repair_summary.get("total_defects", 0))
            aggregated_total_cost += self._safe_float(repair_summary.get("total_estimated_cost", 0))
            aggregated_material_cost += self._safe_float(repair_summary.get("total_material_cost", 0))
            aggregated_labor_cost += self._safe_float(repair_summary.get("total_labor_cost", 0))
            aggregated_equipment_cost += self._safe_float(repair_summary.get("total_equipment_cost", 0))
            currency = repair_summary.get("currency", currency)

            severities = repair_summary.get("severity_distribution", {})
            for key in severity_distribution:
                severity_distribution[key] += int(severities.get(key, 0))

            for defect_id, defect_data in repair_outputs.get("defect_repairs", {}).items():
                all_defect_repairs[defect_id] = defect_data

        combined_summary = {
            "total_defects": aggregated_total_defects,
            "total_estimated_cost": round(aggregated_total_cost, 2),
            "total_material_cost": round(aggregated_material_cost, 2),
            "total_labor_cost": round(aggregated_labor_cost, 2),
            "total_equipment_cost": round(aggregated_equipment_cost, 2),
            "currency": currency,
            "severity_distribution": severity_distribution,
        }

        document = self._build_document(
            title_text="BATCH REPAIR ESTIMATE",
            reference_code=f"MI-BATCH-{batch_id[:8].upper()}",
            vessel_name=vessel_name or "Fleet Inspection",
            repair_summary=combined_summary,
            defect_repairs=all_defect_repairs,
        )

        output_dir = os.path.join("outputs", "batches", batch_id)
        os.makedirs(output_dir, exist_ok=True)
        output_docx_path = os.path.join(output_dir, "combined_vessel_inspection_report.docx")
        document.save(output_docx_path)
        return self._finalize_output(output_docx_path)
