# This is the final, updated content for your file at:
# backend/app/services/document_parser.py

import logging
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiDocumentParser:
    """
    A robust service to parse text content from documents using the Gemini API,
    with built-in retries for network resilience.
    """

    def __init__(self):
        # Ensure the API key is configured before trying to initialize
        if not settings.GEMINI_API_KEY or "YOUR_GEMINI_API_KEY_HERE" in settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured correctly in app/core/config.py.")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
        logger.info("GeminiDocumentParser initialized successfully.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True # Re-raise the exception after the final attempt
    )
    def parse(self, file_path: str, prompt: str = None) -> str:
        """
        Uploads a file to Gemini, generates content based on a prompt,
        and cleans up the file. Returns the extracted text.
        """
        default_prompt = "Extract all text from this document. Preserve the original structure, including paragraphs, headings, and tables, as accurately as possible."
        final_prompt = prompt or default_prompt
        
        uploaded_file = None
        try:
            logger.info(f"Uploading file to Gemini: {file_path}")
            # The API automatically determines the MIME type.
            uploaded_file = genai.upload_file(path=file_path)
            
            logger.info(f"File '{uploaded_file.display_name}' uploaded successfully. Generating content...")
            response = self.model.generate_content([final_prompt, uploaded_file])
            
            logger.info(f"Content generated for '{uploaded_file.display_name}'.")
            return response.text
            
        except Exception as e:
            logger.error(f"An error occurred during Gemini processing for {file_path}: {e}")
            # The @retry decorator will handle re-running this method.
            # If all retries fail, it will raise the final exception.
            raise
        finally:
            # Ensure the uploaded file is always deleted from Gemini's storage
            if uploaded_file:
                logger.info(f"Deleting uploaded file from Gemini: {uploaded_file.name}")
                genai.delete_file(name=uploaded_file.name)

# Create a single instance that can be imported and used elsewhere
try:
    parser = GeminiDocumentParser()
except ValueError as e:
    logger.error(f"Could not initialize GeminiDocumentParser: {e}")
    # Set parser to None if initialization fails. The endpoint will handle this.
    parser = None
