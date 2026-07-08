from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse
import os
import shutil
import subprocess
from dependencies.services import get_inspection_service
from services.inspection_service import InspectionService
from dependencies.services import get_analysis_session_service, get_drydock_visit_service
from services.analysis_session_service import AnalysisSessionService
from services.drydock_visit_service import DrydockVisitService
from fastapi import Depends
from models import InspectionSession
from modules.document_generation_module import DocumentGenerationModule
from services.session_views import load_outputs
from database import get_db
from loguru import logger
router = APIRouter()


def _convert_docx_to_pdf(docx_path: str, pdf_path: str) -> None:
    if os.name == "nt":
        import pythoncom
        pythoncom.CoInitialize()
        try:
            from docx2pdf import convert
            convert(os.path.abspath(docx_path), os.path.abspath(pdf_path))
        finally:
            pythoncom.CoUninitialize()
        return

    soffice_binary = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice_binary:
        raise RuntimeError("LibreOffice headless binary not found")

    output_dir = os.path.dirname(os.path.abspath(pdf_path))
    subprocess.run(
        [
            soffice_binary,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            output_dir,
            os.path.abspath(docx_path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    generated_pdf = os.path.join(
        output_dir,
        f"{os.path.splitext(os.path.basename(docx_path))[0]}.pdf",
    )
    if generated_pdf != os.path.abspath(pdf_path) and os.path.exists(generated_pdf):
        os.replace(generated_pdf, pdf_path)


def _collect_batch_repair_payloads(sessions: list[InspectionSession]) -> list[dict]:
    payloads: list[dict] = []
    for session in sessions:
        outputs = load_outputs(session)
        repair_payload = outputs.get("repair") or {}
        if repair_payload.get("defect_repairs"):
            enriched_payload = dict(repair_payload)
            enriched_payload["vessel_name"] = session.vessel_name or enriched_payload.get("vessel_name")
            payloads.append(enriched_payload)
    return payloads

@router.get("/download/{session_id}")
async def download_report(session_id: str, lang: str = "en", inspection_service: InspectionService = Depends(get_inspection_service)):
    
    session = await inspection_service.repo.find_one({"session_id": session_id})

    if not session:
        return {"error": "Session not found"}

    if lang == "bahasa":
        docx_url = session.get("document_docx_url_bahasa")
        if docx_url and docx_url.startswith("http"):
            return RedirectResponse(f"{docx_url}?download=")
        
        docx_path = session.get("document_path")
        if docx_path:
            bahasa_path = docx_path.replace(".docx", "_bahasa.docx")
            if os.path.exists(bahasa_path):
                return FileResponse(
                    bahasa_path,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    filename="inspection_report_bahasa.docx"
                )

    doc_path = session.get("document_docx_url") or session.get("document_path")
    if not doc_path:
        return {"error": "Document not ready"}

    if doc_path.startswith("http"):
        return RedirectResponse(f"{doc_path}?download=")

    if not os.path.exists(doc_path):
        return {"error": "Document not ready"}

    return FileResponse(
        doc_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="inspection_report.docx"
    )

@router.get("/download/{session_id}/pdf")
async def download_report_pdf(session_id: str, attachment: bool = False, lang: str = "en", inspection_service: InspectionService = Depends(get_inspection_service)):
    
    session = await inspection_service.repo.find_one({"session_id": session_id})

    if not session:
        return {"error": "Session not found"}

    if lang == "bahasa":
        pdf_url = session.get("document_pdf_url_bahasa")
        if pdf_url and pdf_url.startswith("http"):
            if attachment:
                return RedirectResponse(f"{pdf_url}?download=")
            return RedirectResponse(pdf_url)
        
        docx_path = session.get("document_path")
        if docx_path:
            bahasa_pdf_path = docx_path.replace(".docx", "_bahasa.pdf")
            if os.path.exists(bahasa_pdf_path):
                disposition = "attachment" if attachment else "inline"
                return FileResponse(
                    bahasa_pdf_path,
                    media_type="application/pdf",
                    headers={"Content-Disposition": f'{disposition}; filename="inspection_report_bahasa.pdf"'}
                )

    pdf_url = session.get("document_pdf_url")
    if pdf_url and pdf_url.startswith("http"):
        if attachment:
            return RedirectResponse(f"{pdf_url}?download=")
        if ".docx" in pdf_url.lower():
            return RedirectResponse(f"https://docs.google.com/viewer?url={pdf_url}&embedded=true")
        return RedirectResponse(pdf_url)

    docx_path = session.get("document_path")
    if docx_path and docx_path.startswith("http"):
        # For legacy Supabase sessions that only have a docx URL saved in document_path
        if attachment:
            return RedirectResponse(f"{docx_path}?download=")
        # Use Google Docs viewer to render it inline instead of downloading
        viewer_url = f"https://docs.google.com/viewer?url={docx_path}&embedded=true"
        return RedirectResponse(viewer_url)

    if not docx_path or not os.path.exists(docx_path):
        return {"error": "Document not ready"}

    pdf_path = docx_path.replace(".docx", ".pdf")
    
    if not os.path.exists(pdf_path):
        try:
            _convert_docx_to_pdf(docx_path, pdf_path)
        except Exception as e:
            return {"error": f"Failed to generate PDF: {e}"}

    if not os.path.exists(pdf_path):
        return {"error": "Failed to generate PDF"}

    disposition = "attachment" if attachment else "inline"
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="inspection_report.pdf"'}
    )

@router.get("/batches/{batch_id}/download/docx")
async def download_batch_report(
    batch_id: str,
    lang: str = "en",
    inspection_service: InspectionService = Depends(get_inspection_service),
    analysis_session_service: AnalysisSessionService = Depends(get_analysis_session_service),
    drydock_visit_service: DrydockVisitService = Depends(get_drydock_visit_service)
):
    if lang == "bahasa":
        visit_doc = await drydock_visit_service.repo.find_one({"visit_id": batch_id})
        if visit_doc:
            url = visit_doc.get("document_docx_url_bahasa")
            if url and url.startswith("http"):
                return RedirectResponse(f"{url}?download=")
            
            output_dir = os.path.join("outputs", "batches", batch_id)
            bahasa_path = os.path.join(output_dir, "combined_vessel_inspection_report_bahasa.docx")
            if os.path.exists(bahasa_path):
                return FileResponse(
                    bahasa_path,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    filename=f"batch_{batch_id}_inspection_report_bahasa.docx"
                )

    docs = await inspection_service.repo.find_many({"batch_id": batch_id}, sort=[("created_at", 1)])
    if not docs:
        analysis_docs = await analysis_session_service.repo.find_many({"visit_id": batch_id})
        if analysis_docs:
            session_ids = [doc.get("session_id") for doc in analysis_docs if doc.get("session_id")]
            docs = await inspection_service.repo.find_many({"session_id": {"$in": session_ids}}, sort=[("created_at", 1)])

    if not docs:
        return {"error": "Batch not found"}

    sessions = [InspectionSession(**doc) for doc in docs]
    output_dir = os.path.join("outputs", "batches", batch_id)
    output_docx_path = os.path.join(output_dir, "combined_vessel_inspection_report.docx")

    imo_number = sessions[0].imo_number
    if imo_number:
        all_vessel_docs = await inspection_service.repo.find_many({"imo_number": imo_number}, sort=[("created_at", 1)])
        all_sessions = [InspectionSession(**doc) for doc in all_vessel_docs]
    else:
        all_sessions = sessions

    repair_payloads = _collect_batch_repair_payloads(all_sessions)
    vessel_name = all_sessions[0].vessel_name or "Combined Vessel Inspection"

    generator = DocumentGenerationModule()
    generator.create_batch_report_from_payloads(batch_id, repair_payloads, vessel_name)
        
    if not os.path.exists(output_docx_path):
         return {"error": "Failed to generate report"}

    return FileResponse(
        output_docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"batch_{batch_id}_inspection_report.docx"
    )

@router.get("/batches/{batch_id}/download/pdf")
async def download_batch_report_pdf(
    batch_id: str,
    attachment: bool = False,
    lang: str = "en",
    inspection_service: InspectionService = Depends(get_inspection_service),
    analysis_session_service: AnalysisSessionService = Depends(get_analysis_session_service),
    drydock_visit_service: DrydockVisitService = Depends(get_drydock_visit_service)
):
    if lang == "bahasa":
        visit_doc = await drydock_visit_service.repo.find_one({"visit_id": batch_id})
        if visit_doc:
            url = visit_doc.get("document_pdf_url_bahasa")
            if url and url.startswith("http"):
                if attachment:
                    return RedirectResponse(f"{url}?download=")
                return RedirectResponse(url)
            
            output_dir = os.path.join("outputs", "batches", batch_id)
            bahasa_pdf_path = os.path.join(output_dir, "combined_vessel_inspection_report_bahasa.pdf")
            if os.path.exists(bahasa_pdf_path):
                disposition = "attachment" if attachment else "inline"
                return FileResponse(
                    bahasa_pdf_path,
                    media_type="application/pdf",
                    headers={"Content-Disposition": f'{disposition}; filename="batch_{batch_id}_inspection_report_bahasa.pdf"'}
                )

    docs = await inspection_service.repo.find_many({"batch_id": batch_id}, sort=[("created_at", 1)])
    
    if not docs:
        analysis_docs = await analysis_session_service.repo.find_many({"visit_id": batch_id})
        if analysis_docs:
            session_ids = [doc.get("session_id") for doc in analysis_docs if doc.get("session_id")]
            docs = await inspection_service.repo.find_many({"session_id": {"$in": session_ids}}, sort=[("created_at", 1)])

    if not docs:
        return {"error": "Batch not found"}

    sessions = [InspectionSession(**doc) for doc in docs]
    
    output_dir = os.path.join("outputs", "batches", batch_id)
    output_docx_path = os.path.join(output_dir, "combined_vessel_inspection_report.docx")
    output_pdf_path = os.path.join(output_dir, "combined_vessel_inspection_report.pdf")

    imo_number = sessions[0].imo_number
    if imo_number:
        all_vessel_docs = await inspection_service.repo.find_many({"imo_number": imo_number}, sort=[("created_at", 1)])
        all_sessions = [InspectionSession(**doc) for doc in all_vessel_docs]
    else:
        all_sessions = sessions

    repair_payloads = _collect_batch_repair_payloads(all_sessions)
    vessel_name = all_sessions[0].vessel_name or "Combined Vessel Inspection"

    generator = DocumentGenerationModule()
    generator.create_batch_report_from_payloads(batch_id, repair_payloads, vessel_name)
        
    if not os.path.exists(output_docx_path):
         return {"error": "Failed to generate report"}

    try:
        _convert_docx_to_pdf(output_docx_path, output_pdf_path)
    except Exception as e:
        return {"error": f"Failed to generate PDF: {e}"}

    if not os.path.exists(output_pdf_path):
        return {"error": "Failed to generate PDF"}

    disposition = "attachment" if attachment else "inline"
    return FileResponse(
        output_pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="batch_{batch_id}_inspection_report.pdf"'}
    )

@router.get("/reports/{inspection_id}/language")
async def get_report_language(
    inspection_id: str,
    lang: str = "en",
    db = Depends(get_db)
):
    from services.report_language_service import ReportLanguageService
    try:
        res = await ReportLanguageService.get_or_generate_report(inspection_id, lang, db)
        return res
    except Exception as e:
        logger.error(f"Failed to get/generate report for lang {lang}: {e}")
        return {"error": str(e)}
