# This is the final, updated content for your file at:
# backend/app/services/document_parser.py

import os
import tempfile
from pathlib import Path
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential
import fitz  # PyMuPDF for PDF image extraction
from docx import Document as DocxDocument
from PIL import Image
import io

from app.core.config import settings
from app.core.logging import LoggerMixin
from app.services.ai.prompt_manager import prompt_manager, PromptType

class MultiModalDocumentParser(LoggerMixin):
    """
    A robust service to parse text content from documents using the Gemini API,
    with built-in retries for network resilience, fallback for unsupported formats,
    and multi-modal capabilities for image extraction and analysis.
    """

    def __init__(self):
        """Initializes the MultiModalDocumentParser."""
        super().__init__()
        
        if not settings.GEMINI_API_KEY or "YOUR_GEMINI_API_KEY_HERE" in settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured correctly in app/core/config.py.")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        self.vision_model = genai.GenerativeModel(settings.GEMINI_VISION_MODEL)
        self.logger.info("MultiModalDocumentParser initialized successfully.")

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

    def _extract_images_from_pdf(self, file_path: str) -> list:
        """
        Extract images from PDF files using PyMuPDF.
        Returns a list of image data and metadata.
        """
        images = []
        try:
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        
                        if pix.n - pix.alpha < 4:  # GRAY or RGB
                            img_data = pix.tobytes("png")
                            images.append({
                                'page': page_num + 1,
                                'index': img_index,
                                'data': img_data,
                                'format': 'png',
                                'width': pix.width,
                                'height': pix.height
                            })
                        else:  # CMYK: convert to RGB first
                            pix1 = fitz.Pixmap(fitz.csRGB, pix)
                            img_data = pix1.tobytes("png")
                            images.append({
                                'page': page_num + 1,
                                'index': img_index,
                                'data': img_data,
                                'format': 'png',
                                'width': pix1.width,
                                'height': pix1.height
                            })
                            pix1 = None
                        pix = None
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to extract image {img_index} from page {page_num + 1}: {e}")
                        continue
            
            doc.close()
            self.logger.info(f"Extracted {len(images)} images from PDF")
            return images
            
        except Exception as e:
            self.logger.error(f"Error extracting images from PDF: {e}")
            return []

    def _extract_images_from_docx(self, file_path: str) -> list:
        """
        Extract images from DOCX files using python-docx.
        Returns a list of image data and metadata.
        """
        images = []
        try:
            doc = DocxDocument(file_path)
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    try:
                        image_data = rel.target_part.blob
                        images.append({
                            'data': image_data,
                            'format': 'png',  # Default format
                            'width': None,
                            'height': None
                        })
                    except Exception as e:
                        self.logger.warning(f"Failed to extract image from DOCX: {e}")
                        continue
            
            self.logger.info(f"Extracted {len(images)} images from DOCX")
            return images
            
        except Exception as e:
            self.logger.error(f"Error extracting images from DOCX: {e}")
            return []

    async def _analyze_image_with_vision(self, image_data: bytes, image_index: int) -> str:
        """
        Analyze an image using Gemini Vision API.
        Returns a textual description of the image.
        """
        try:
            # Use the prompt manager for image analysis
            prompt = prompt_manager.get_prompt(PromptType.IMAGE_ANALYSIS)
            
            # Create image object for Gemini
            image = Image.open(io.BytesIO(image_data))
            
            # Generate content with image
            response = await self.vision_model.generate_content([prompt, image])
            
            description = response.text
            self.logger.debug(f"Image {image_index} analyzed successfully")
            
            return f"[image-{image_index:02d}: {description}]"
            
        except Exception as e:
            self.logger.error(f"Error analyzing image {image_index}: {e}")
            return f"[image-{image_index:02d}: Image analysis failed]"

    def _convert_docx_to_text(self, file_path: str) -> str:
        """
        Convert DOCX files to plain text using python-docx.
        """
        try:
            doc = DocxDocument(file_path)
            text_content = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text)
            
            # Also extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            text_content.append(cell.text)
            
            converted_text = "\n".join(text_content)
            self.logger.info(f"Successfully converted DOCX to text ({len(converted_text)} characters)")
            return converted_text
            
        except Exception as e:
            self.logger.error(f"Error converting DOCX to text: {e}")
            raise ValueError(f"Failed to convert DOCX file: {e}")

    def _convert_doc_to_text(self, file_path: str) -> str:
        """
        Convert DOC files to plain text using docx2txt.
        """
        try:
            import docx2txt
            text_content = docx2txt.process(file_path)
            
            if not text_content or not text_content.strip():
                raise ValueError("No text content extracted from DOC file")
            
            self.logger.info(f"Successfully converted DOC to text ({len(text_content)} characters)")
            return text_content.strip()
            
        except ImportError:
            self.logger.error("docx2txt not available for DOC conversion")
            raise ValueError("DOC conversion requires docx2txt package")
        except Exception as e:
            self.logger.error(f"Error converting DOC to text: {e}")
            raise ValueError(f"Failed to convert DOC file: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _process_with_gemini(self, file_path: str, mime_type: str, prompt: str) -> str:
        """
        Process a file with Gemini API with retry logic.
        """
        try:
            with open(file_path, 'rb') as file:
                response = await self.model.generate_content([prompt, file])
                return response.text
        except Exception as e:
            self.logger.error(f"Error processing file with Gemini: {e}")
            raise

    async def parse_with_images(self, file_path: str) -> str:
        """
        Parse a document and extract text content, including image analysis.
        This is the main method that orchestrates the entire parsing process.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_path = str(file_path)
        extension = self._get_file_extension(file_path)
        
        self.logger.info(f"Starting document parsing for: {file_path} (type: {extension})")
        
        try:
            # Handle files that require conversion first
            if self._requires_conversion(file_path):
                self.logger.info(f"Converting {extension} file to text")
                
                if extension == ".docx":
                    converted_text = self._convert_docx_to_text(file_path)
                elif extension == ".doc":
                    converted_text = self._convert_doc_to_text(file_path)
                else:
                    raise ValueError(f"Unsupported file type requiring conversion: {extension}")
                
                # For converted files, return the text directly (no need for Gemini processing)
                return converted_text
            
            # Handle directly supported files
            elif self._is_supported_directly(file_path):
                processing_path = file_path
                mime_type = SUPPORTED_MIME_TYPES[extension]
                
                # Extract and analyze images for supported formats
                if extension == ".pdf":
                    images = self._extract_images_from_pdf(file_path)
                    if images:
                        self.logger.info(f"Found {len(images)} images in PDF, analyzing with vision...")
                        image_descriptions = []
                        for i, img in enumerate(images):
                            description = await self._analyze_image_with_vision(img['data'], i)
                            image_descriptions.append(description)
                        
                        # Process the PDF text first
                        pdf_text = await self._process_with_gemini(processing_path, mime_type, "Extract all text content from this document.")
                        
                        # Append image descriptions
                        if pdf_text and image_descriptions:
                            pdf_text += "\n\n" + "\n".join(image_descriptions)
                        
                        return pdf_text
                
                # For other supported formats, process with Gemini
                return await self._process_with_gemini(processing_path, mime_type, "Extract all text content from this document.")
                
            else:
                # Unsupported file type
                error_message = f"Unsupported file type: {extension}. Supported types: {list(SUPPORTED_MIME_TYPES.keys())} and {list(CONVERSION_REQUIRED.keys())}"
                self.logger.error(error_message)
                raise ValueError(error_message)
                
        except Exception as e:
            self.logger.error(f"Error parsing document {file_path}: {e}")
            raise
        finally:
            # Clean up any temporary files if needed
            pass

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