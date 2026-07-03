from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse
import os
from dependencies.services import get_inspection_service
from services.inspection_service import InspectionService
from dependencies.services import get_analysis_session_service, get_drydock_visit_service
from services.analysis_session_service import AnalysisSessionService
from services.drydock_visit_service import DrydockVisitService
from fastapi import Depends
from models import InspectionSession
from modules.document_generation_module import DocumentGenerationModule
router = APIRouter()

@router.get("/download/{session_id}")
async def download_report(session_id: str, inspection_service: InspectionService = Depends(get_inspection_service)):
    
    session = await inspection_service.repo.find_one({"session_id": session_id})

    if not session:
        return {"error": "Session not found"}

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
async def download_report_pdf(session_id: str, attachment: bool = False, inspection_service: InspectionService = Depends(get_inspection_service)):
    
    session = await inspection_service.repo.find_one({"session_id": session_id})

    if not session:
        return {"error": "Session not found"}

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
            import pythoncom
            pythoncom.CoInitialize()
            try:
                from docx2pdf import convert
                convert(os.path.abspath(docx_path), os.path.abspath(pdf_path))
            finally:
                pythoncom.CoUninitialize()
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
async def download_batch_report(batch_id: str, inspection_service: InspectionService = Depends(get_inspection_service), analysis_session_service: AnalysisSessionService = Depends(get_analysis_session_service)):
    
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
    
    if not os.path.exists(output_docx_path):
        imo_number = sessions[0].imo_number
        if imo_number:
            all_vessel_docs = await inspection_service.repo.find_many({"imo_number": imo_number}, sort=[("created_at", 1)])
            all_sessions = [InspectionSession(**doc) for doc in all_vessel_docs]
        else:
            all_sessions = sessions

        repair_json_paths = []
        for session in all_sessions:
            if session.output_path:
                repair_json_paths.append(os.path.join(session.output_path, "module_5_repair_estimation_output", "repair_estimation_outputs.json"))
        
        vessel_name = all_sessions[0].vessel_name or "Combined Vessel Inspection"
        
        generator = DocumentGenerationModule()
        generator.create_batch_report(batch_id, repair_json_paths, vessel_name)
        
    if not os.path.exists(output_docx_path):
         return {"error": "Failed to generate report"}

    return FileResponse(
        output_docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"batch_{batch_id}_inspection_report.docx"
    )

@router.get("/batches/{batch_id}/download/pdf")
async def download_batch_report_pdf(batch_id: str, attachment: bool = False, inspection_service: InspectionService = Depends(get_inspection_service), analysis_session_service: AnalysisSessionService = Depends(get_analysis_session_service)):
    
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
    
    if not os.path.exists(output_docx_path):
        imo_number = sessions[0].imo_number
        if imo_number:
            # Fetch ALL sessions for this vessel to include in the report
            all_vessel_docs = await inspection_service.repo.find_many({"imo_number": imo_number}, sort=[("created_at", 1)])
            all_sessions = [InspectionSession(**doc) for doc in all_vessel_docs]
        else:
            all_sessions = sessions

        repair_json_paths = []
        for session in all_sessions:
            if session.output_path:
                repair_json_paths.append(os.path.join(session.output_path, "module_5_repair_estimation_output", "repair_estimation_outputs.json"))
        
        vessel_name = all_sessions[0].vessel_name or "Combined Vessel Inspection"
        
        from modules.document_generation_module import DocumentGenerationModule
        generator = DocumentGenerationModule()
        generator.create_batch_report(batch_id, repair_json_paths, vessel_name)
        
    if not os.path.exists(output_docx_path):
         return {"error": "Failed to generate report"}

    if not os.path.exists(output_pdf_path):
        try:
            import pythoncom
            pythoncom.CoInitialize()
            try:
                from docx2pdf import convert
                convert(os.path.abspath(output_docx_path), os.path.abspath(output_pdf_path))
            finally:
                pythoncom.CoUninitialize()
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