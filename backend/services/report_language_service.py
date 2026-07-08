import os
from loguru import logger
from models import InspectionSession, DryDockVisit
from services.supabase_service import supabase_service
from services.session_views import load_outputs
from modules.document_generation_module import DocumentGenerationModule

def _convert_docx_to_pdf(docx_path: str, pdf_path: str) -> None:
    import shutil
    import subprocess
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

class ReportLanguageService:
    @staticmethod
    async def get_or_generate_report(inspection_id: str, lang: str, db) -> dict:
        from repositories.inspection_repo import InspectionRepository
        from repositories.drydock_visit_repo import DrydockVisitRepository
        from repositories.analysis_session_repo import AnalysisSessionRepository
        
        inspection_repo = InspectionRepository(db)
        visit_repo = DrydockVisitRepository(db)
        analysis_repo = AnalysisSessionRepository(db)
        
        # Check if it is a single session
        session_doc = await inspection_repo.find_one({"session_id": inspection_id})
        
        if session_doc:
            session = InspectionSession(**session_doc)
            if lang == "en" or lang != "bahasa":
                logger.info(f"REPORT LANGUAGE REQUESTED - Language: English - Session ID: {inspection_id}")
                return {
                    "document_docx_url": session.document_docx_url or f"/api/v1/download/{inspection_id}",
                    "document_pdf_url": session.document_pdf_url or f"/api/v1/download/{inspection_id}/pdf"
                }
            
            # lang == "bahasa"
            logger.info(f"REPORT LANGUAGE REQUESTED - Language: Bahasa - Session ID: {inspection_id}")
            logger.info("Checking cache...")
            if getattr(session, "document_docx_url_bahasa", None) and getattr(session, "document_pdf_url_bahasa", None):
                logger.info("Bahasa report found in cache. Returning cached version.")
                return {
                    "document_docx_url": session.document_docx_url_bahasa,
                    "document_pdf_url": session.document_pdf_url_bahasa
                }
            
            logger.info("Bahasa report not found. Generating...")
            
            docx_path = session.document_path
            if docx_path and os.path.exists(docx_path) and not docx_path.startswith("http"):
                output_dir = os.path.dirname(docx_path)
            else:
                output_dir = os.path.join("outputs", "sessions", inspection_id, "module_8_report_generation_output")
            os.makedirs(output_dir, exist_ok=True)
            
            # Load outputs payload
            outputs = load_outputs(session)
            repair_payload = outputs.get("repair") or {}
            
            # Temporarily disable Supabase upload inside generator
            orig_is_configured = supabase_service.is_configured
            supabase_service.is_configured = lambda: False
            try:
                generator = DocumentGenerationModule(output_folder=output_dir)
                generator.create_report(repair_payload, lang="bahasa")
            finally:
                supabase_service.is_configured = orig_is_configured
            
            local_docx_path = os.path.join(output_dir, "vessel_inspection_report_bahasa.docx")
            local_pdf_path = os.path.join(output_dir, "vessel_inspection_report_bahasa.pdf")
            
            logger.info("Converting DOCX to PDF...")
            _convert_docx_to_pdf(local_docx_path, local_pdf_path)
            
            logger.info("DOCX Generated. PDF Generated.")
            
            # Upload to Supabase if configured
            if supabase_service.is_configured():
                logger.info("Uploading to Supabase...")
                docx_url = supabase_service.upload_file(
                    local_docx_path,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                pdf_url = supabase_service.upload_file(
                    local_pdf_path,
                    "application/pdf"
                )
                logger.info("Uploaded to Supabase.")
            else:
                docx_url = f"/api/v1/download/{inspection_id}?lang=bahasa"
                pdf_url = f"/api/v1/download/{inspection_id}/pdf?lang=bahasa"
                
            # Update cache in Mongo
            await inspection_repo.update(
                {"session_id": inspection_id},
                {
                    "document_docx_url_bahasa": docx_url,
                    "document_pdf_url_bahasa": pdf_url
                }
            )
            logger.info("URLs Saved.")
            return {
                "document_docx_url": docx_url,
                "document_pdf_url": pdf_url
            }
            
        else:
            # Check if it is a batch
            visit_doc = await visit_repo.find_one({"visit_id": inspection_id})
            
            if visit_doc:
                visit = DryDockVisit(**visit_doc)
                if lang == "en" or lang != "bahasa":
                    logger.info(f"REPORT LANGUAGE REQUESTED - Language: English - Batch ID: {inspection_id}")
                    return {
                        "document_docx_url": f"/api/v1/batches/{inspection_id}/download/docx",
                        "document_pdf_url": f"/api/v1/batches/{inspection_id}/download/pdf"
                    }
                
                # lang == "bahasa"
                logger.info(f"REPORT LANGUAGE REQUESTED - Language: Bahasa - Batch ID: {inspection_id}")
                logger.info("Checking cache...")
                if getattr(visit, "document_docx_url_bahasa", None) and getattr(visit, "document_pdf_url_bahasa", None):
                    logger.info("Bahasa batch report found in cache. Returning cached version.")
                    return {
                        "document_docx_url": visit.document_docx_url_bahasa,
                        "document_pdf_url": visit.document_pdf_url_bahasa
                    }
                
                logger.info("Bahasa batch report not found. Generating...")
                
                # Load sessions
                docs = await inspection_repo.find_many({"batch_id": inspection_id}, sort=[("created_at", 1)])
                if not docs:
                    analysis_docs = await analysis_repo.find_many({"visit_id": inspection_id})
                    if analysis_docs:
                        session_ids = [doc.get("session_id") for doc in analysis_docs if doc.get("session_id")]
                        docs = await inspection_repo.find_many({"session_id": {"$in": session_ids}}, sort=[("created_at", 1)])
                
                if not docs:
                    raise Exception("No sessions found for this batch.")
                
                sessions = [InspectionSession(**doc) for doc in docs]
                imo_number = sessions[0].imo_number
                if imo_number:
                    all_vessel_docs = await inspection_repo.find_many({"imo_number": imo_number}, sort=[("created_at", 1)])
                    all_sessions = [InspectionSession(**doc) for doc in all_vessel_docs]
                else:
                    all_sessions = sessions
                
                repair_payloads = _collect_batch_repair_payloads(all_sessions)
                vessel_name = all_sessions[0].vessel_name or "Combined Vessel Inspection"
                
                output_dir = os.path.join("outputs", "batches", inspection_id)
                os.makedirs(output_dir, exist_ok=True)
                
                # Temporarily disable Supabase upload inside generator
                orig_is_configured = supabase_service.is_configured
                supabase_service.is_configured = lambda: False
                try:
                    generator = DocumentGenerationModule(output_folder=output_dir)
                    generator.create_batch_report_from_payloads(inspection_id, repair_payloads, vessel_name, lang="bahasa")
                finally:
                    supabase_service.is_configured = orig_is_configured
                
                local_docx_path = os.path.join(output_dir, "combined_vessel_inspection_report_bahasa.docx")
                local_pdf_path = os.path.join(output_dir, "combined_vessel_inspection_report_bahasa.pdf")
                
                logger.info("Converting DOCX to PDF...")
                _convert_docx_to_pdf(local_docx_path, local_pdf_path)
                
                logger.info("DOCX Generated. PDF Generated.")
                
                # Upload to Supabase if configured
                if supabase_service.is_configured():
                    logger.info("Uploading to Supabase...")
                    docx_url = supabase_service.upload_file(
                        local_docx_path,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                    pdf_url = supabase_service.upload_file(
                        local_pdf_path,
                        "application/pdf"
                    )
                    logger.info("Uploaded to Supabase.")
                else:
                    docx_url = f"/api/v1/batches/{inspection_id}/download/docx?lang=bahasa"
                    pdf_url = f"/api/v1/batches/{inspection_id}/download/pdf?lang=bahasa"
                
                # Update cache in Mongo
                await visit_repo.update(
                    {"visit_id": inspection_id},
                    {
                        "document_docx_url_bahasa": docx_url,
                        "document_pdf_url_bahasa": pdf_url
                    }
                )
                logger.info("URLs Saved.")
                return {
                    "document_docx_url": docx_url,
                    "document_pdf_url": pdf_url
                }
            
            raise Exception("Inspection ID not found.")
