import os
import logging
import asyncio
import threading
from app.config import settings
from app.tasks.celery_app import celery_app
from app.services.extractor import DocumentExtractorService
from app.services.segmenter import SentenceSegmenterService
from app.services.matcher import DualTierMatcher

logger = logging.getLogger(__name__)

def run_async_in_thread(func, *args, **kwargs):
    """Runs an async function inside a separate thread with an isolated event loop to prevent Windows Errno 22 conflict."""
    res = None
    err = None
    
    def target():
        nonlocal res, err
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                res = loop.run_until_complete(func(*args, **kwargs))
            finally:
                loop.close()
        except Exception as e:
            err = e
            
    t = threading.Thread(target=target)
    t.start()
    t.join()
    
    if err:
        raise err
    return res

@celery_app.task(bind=True, name="app.tasks.analysis.analyze_document_task")
def analyze_document_task(self, file_path: str = None, original_filename: str = None, *args, **kwargs) -> dict:
    """
    Background Celery task to parse a document, fetch web references, and perform plagiarism analysis.
    """
    # Handle flexible argument positioning under Celery Eager mode
    pos_args = [a for a in ([file_path, original_filename] + list(args)) if a is not None]
    if pos_args:
        file_path = str(pos_args[0])
        original_filename = str(pos_args[1]) if len(pos_args) > 1 else Path(file_path).name

    logger.info(f"Starting analysis task for file: {original_filename} (temp path: {file_path})")
    job_id = getattr(self.request, "id", None) or str(uuid.uuid4())
    
    try:
        # Read the file from disk with retries for Windows file lock release
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Temporary file not found at: {file_path}")
            
        content = None
        for attempt in range(5):
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                break
            except OSError:
                import time
                time.sleep(0.1)
                
        if content is None:
            with open(file_path, "rb") as f:
                content = f.read()
        
        # Run extractor
        text = DocumentExtractorService.extract_text(original_filename, content)
        
        # Segment sentences
        sentences_data = SentenceSegmenterService.segment(text)
        
        # Format sentences
        sentences = [
            {
                "text": s["text"],
                "start_char": s["start_char"],
                "end_char": s["end_char"]
            }
            for s in sentences_data
        ]
        
        # 1. Ephemeral online candidate retrieval & caching
        if settings.ENABLE_ONLINE_RETRIEVAL:
            try:
                from app.services.online_retriever import OnlineRetrieverService
                logger.info(f"Triggering online retrieval query generation for job: {job_id}")
                queries = OnlineRetrieverService.extract_search_queries(text)
                
                logger.info(f"Generated search queries: {queries}")
                candidates = run_async_in_thread(OnlineRetrieverService.get_online_candidates, queries)
                
                run_async_in_thread(OnlineRetrieverService.seed_ephemeral_candidates, job_id, candidates)
            except Exception as e:
                logger.error(f"Failed to fetch/cache online candidate papers: {e}")

        # 2. Run dual-tier plagiarism matcher
        matcher = DualTierMatcher()
        analysis_report = matcher.analyze_document(sentences_data, job_id=job_id)
        
        # Return complete results in the same structure as DocumentUploadResponse
        result = {
            "filename": original_filename,
            "text": text,
            "char_count": len(text),
            "sentence_count": len(sentences),
            "sentences": sentences,
            "analysis": analysis_report
        }
        return result
        
    except Exception as e:
        logger.error(f"Error in analyze_document_task: {str(e)}", exc_info=True)
        raise e
        
    finally:
        # 3. Clean up the temporary uploaded file from disk
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Successfully deleted temp file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temp file {file_path}: {e}")
                
        # 4. Prune ephemeral database & Elasticsearch candidate records
        if settings.ENABLE_ONLINE_RETRIEVAL:
            try:
                from app.services.online_retriever import OnlineRetrieverService
                OnlineRetrieverService.prune_cache(job_id)
            except Exception as e:
                logger.error(f"Failed to prune cache for job {job_id}: {e}")
