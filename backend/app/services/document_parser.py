# This is the final, updated content for your file at:
# backend/app/services/document_parser.py

import logging
import os
import tempfile
from pathlib import Path
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# A dictionary to map file extensions to their correct MIME types
# This ensures we send a supported MIME type to the Gemini API
SUPPORTED_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/plain",
    ".html": "text/html",
    ".xml": "application/xml",
    # Note: DOCX is not directly supported by Gemini API
}

# File types that require conversion before processing
CONVERSION_REQUIRED = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
}

class GeminiDocumentParser:
    """
    A robust service to parse text content from documents using the Gemini API,
    with built-in retries for network resilience and fallback for unsupported formats.
    """

    def __init__(self):
        """Initializes the GeminiDocumentParser."""
        if not settings.GEMINI_API_KEY or "YOUR_GEMINI_API_KEY_HERE" in settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured correctly in app/core/config.py.")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
        logger.info("GeminiDocumentParser initialized successfully.")

    def _get_file_extension(self, file_path: str) -> str:
        """Get the file extension in lowercase."""
        return os.path.splitext(file_path)[1].lower()

    def _is_supported_directly(self, file_path: str) -> bool:
        """Check if the file type is directly supported by Gemini API."""
        extension = self._get_file_extension(file_path)
        return extension in SUPPORTED_MIME_TYPES

    def _requires_conversion(self, file_path: str) -> bool:
        """Check if the file type requires conversion."""
        extension = self._get_file_extension(file_path)
        return extension in CONVERSION_REQUIRED

    def _convert_docx_to_text(self, file_path: str) -> str:
        """
        Convert DOCX file to plain text using python-docx.
        This is a fallback for when Gemini API doesn't support DOCX directly.
        """
        try:
            # Import python-docx here to avoid dependency issues if not installed
            from docx import Document
            
            logger.info(f"Converting DOCX to text: {file_path}")
            doc = Document(file_path)
            
            # Extract text from paragraphs
            text_content = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text)
            
            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text.strip())
                    if row_text:
                        text_content.append(" | ".join(row_text))
            
            full_text = "\n".join(text_content)
            logger.info(f"Successfully converted DOCX to text. Length: {len(full_text)} characters")
            return full_text
            
        except ImportError:
            logger.error("python-docx is not installed. Cannot convert DOCX files.")
            raise ValueError("DOCX conversion not available. Install python-docx to enable DOCX support.")
        except Exception as e:
            logger.error(f"Error converting DOCX file {file_path}: {e}")
            raise ValueError(f"Failed to convert DOCX file: {e}")

    def _convert_doc_to_text(self, file_path: str) -> str:
        """
        Convert DOC file to plain text using python-docx2txt.
        This is a fallback for when Gemini API doesn't support DOC directly.
        """
        try:
            # Import docx2txt here to avoid dependency issues if not installed
            import docx2txt
            
            logger.info(f"Converting DOC to text: {file_path}")
            text_content = docx2txt.process(file_path)
            logger.info(f"Successfully converted DOC to text. Length: {len(text_content)} characters")
            return text_content
            
        except ImportError:
            logger.error("docx2txt is not installed. Cannot convert DOC files.")
            raise ValueError("DOC conversion not available. Install docx2txt to enable DOC support.")
        except Exception as e:
            logger.error(f"Error converting DOC file {file_path}: {e}")
            raise ValueError(f"Failed to convert DOC file: {e}")

    def _create_text_file_for_gemini(self, content: str) -> str:
        """Create a temporary text file with the converted content for Gemini processing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write(content)
            return tmp_file.name

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    def parse(self, file_path: str, prompt: str = None) -> str:
        """
        Parse text content from a document. Handles both directly supported formats
        and files that require conversion (like DOCX).
        """
        default_prompt = "Extract all text from this document. Preserve the original structure, including paragraphs, headings, and tables, as accurately as possible."
        final_prompt = prompt or default_prompt
        
        extension = self._get_file_extension(file_path)
        temp_file_path = None
        
        try:
            # Handle files that require conversion
            if self._requires_conversion(file_path):
                if extension == ".docx":
                    converted_text = self._convert_docx_to_text(file_path)
                elif extension == ".doc":
                    converted_text = self._convert_doc_to_text(file_path)
                else:
                    raise ValueError(f"Unsupported file type requiring conversion: {extension}")
                
                # Create a temporary text file for Gemini processing
                temp_file_path = self._create_text_file_for_gemini(converted_text)
                processing_path = temp_file_path
                mime_type = "text/plain"
                
            # Handle directly supported files
            elif self._is_supported_directly(file_path):
                processing_path = file_path
                mime_type = SUPPORTED_MIME_TYPES[extension]
                
            else:
                # Unsupported file type
                error_message = f"Unsupported file type: {extension}. Supported types: {list(SUPPORTED_MIME_TYPES.keys())} and {list(CONVERSION_REQUIRED.keys())}"
                logger.error(error_message)
                raise ValueError(error_message)

            # Process the file with Gemini
            return self._process_with_gemini(processing_path, mime_type, final_prompt)
            
        finally:
            # Clean up temporary file if created
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    logger.info(f"Cleaned up temporary file: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file_path}: {e}")

    def _process_with_gemini(self, file_path: str, mime_type: str, prompt: str) -> str:
        """Process a file with the Gemini API."""
        uploaded_file = None
        try:
            logger.info(f"Uploading file to Gemini: {file_path} with MIME type: {mime_type}")
            uploaded_file = genai.upload_file(path=file_path, mime_type=mime_type)
            
            logger.info(f"File '{uploaded_file.display_name}' uploaded successfully. Generating content...")
            response = self.model.generate_content([prompt, uploaded_file])
            
            logger.info(f"Content generated for '{uploaded_file.display_name}'.")
            return response.text
            
        except Exception as e:
            logger.error(f"An error occurred during Gemini processing for {file_path}: {e}")
            raise
        finally:
            # Ensure the uploaded file is always deleted from Gemini's storage
            if uploaded_file:
                try:
                    logger.info(f"Deleting uploaded file from Gemini: {uploaded_file.name}")
                    genai.delete_file(name=uploaded_file.name)
                except Exception as e:
                    logger.warning(f"Failed to delete uploaded file {uploaded_file.name}: {e}")

# Create a single instance that can be imported and used elsewhere
try:
    parser = GeminiDocumentParser()
except ValueError as e:
    logger.error(f"Could not initialize GeminiDocumentParser: {e}")
    # Set parser to None if initialization fails. The endpoint will handle this.
    parser = None