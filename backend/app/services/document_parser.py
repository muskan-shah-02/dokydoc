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
import asyncio  # <--- CRITICAL IMPORT

from app.core.config import settings
from app.core.logging import LoggerMixin
from app.services.ai.prompt_manager import prompt_manager, PromptType

class MultiModalDocumentParser(LoggerMixin):
    """
    A robust service to parse text content from documents using the Gemini API.
    """

    def __init__(self):
        super().__init__()
        
        if not settings.GEMINI_API_KEY or "YOUR_GEMINI_API_KEY_HERE" in settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured correctly in app/core/config.py.")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        self.vision_model = genai.GenerativeModel(settings.GEMINI_VISION_MODEL)
        self.logger.info("MultiModalDocumentParser initialized successfully.")

    def _get_file_extension(self, file_path: str) -> str:
        return os.path.splitext(file_path)[1].lower()

    def _is_supported_directly(self, file_path: str) -> bool:
        extension = self._get_file_extension(file_path)
        return extension in SUPPORTED_MIME_TYPES

    def _requires_conversion(self, file_path: str) -> bool:
        extension = self._get_file_extension(file_path)
        return extension in CONVERSION_REQUIRED

    def _extract_images_from_pdf(self, file_path: str) -> list:
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
                        if pix.n - pix.alpha < 4: img_data = pix.tobytes("png")
                        else: 
                             pix1 = fitz.Pixmap(fitz.csRGB, pix)
                             img_data = pix1.tobytes("png")
                             pix1 = None
                        images.append({'page': page_num + 1, 'index': img_index, 'data': img_data, 'format': 'png'})
                        pix = None
                    except Exception: continue
            doc.close()
            return images
        except Exception as e:
            self.logger.error(f"Error extracting images from PDF: {e}")
            return []

    def _extract_images_from_docx(self, file_path: str) -> list:
        images = []
        try:
            doc = DocxDocument(file_path)
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    try:
                        images.append({'data': rel.target_part.blob, 'format': 'png', 'width': None, 'height': None})
                    except Exception: continue
            return images
        except Exception as e:
            self.logger.error(f"Error extracting images from DOCX: {e}")
            return []

    async def _analyze_image_with_vision(self, image_data: bytes, image_index: int) -> str:
        """
        Analyze an image using Gemini Vision API.
        Wraps the synchronous call in a thread to be async-compatible.
        """
        try:
            prompt = prompt_manager.get_prompt(PromptType.IMAGE_ANALYSIS)
            image = Image.open(io.BytesIO(image_data))
            
            # FIX: Run synchronous SDK call in a thread
            response = await asyncio.to_thread(
                self.vision_model.generate_content, [prompt, image]
            )
            
            return f"[image-{image_index:02d}: {response.text}]"
        except Exception as e:
            self.logger.error(f"Error analyzing image {image_index}: {e}")
            return f"[image-{image_index:02d}: Image analysis failed]"

    def _convert_docx_to_text(self, file_path: str) -> str:
        try:
            doc = DocxDocument(file_path)
            text_content = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip(): text_content.append(cell.text)
            return "\n".join(text_content)
        except Exception as e:
            raise ValueError(f"Failed to convert DOCX file: {e}")

    def _convert_doc_to_text(self, file_path: str) -> str:
        try:
            import docx2txt
            return docx2txt.process(file_path).strip()
        except Exception as e:
            raise ValueError(f"Failed to convert DOC file: {e}")

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=2, min=4, max=60)
    )
    async def _process_with_gemini(self, file_path: str, mime_type: str, prompt: str) -> tuple[str, int, int]:
        """
        Process a file with Gemini API with retry logic.
        FIXED: Uses asyncio.to_thread to handle synchronous SDK calls.

        Returns:
            Tuple[str, int, int]: (text, input_tokens, output_tokens)
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()

            # Prepare arguments for the sync call
            args = []
            if mime_type.startswith("text/"):
                try:
                    text_content = file_data.decode("utf-8")
                except UnicodeDecodeError:
                    text_content = file_data.decode("latin-1", errors="replace")
                args = [prompt, text_content]
            else:
                doc_blob = {"mime_type": mime_type, "data": file_data}
                args = [prompt, doc_blob]

            # --- CRITICAL FIX START ---
            # Run the blocking synchronous Google call in a separate thread
            # This allows 'await' to work correctly without crashing the worker
            response = await asyncio.to_thread(self.model.generate_content, args)
            # --- CRITICAL FIX END ---

            # Extract token counts from usage_metadata
            input_tokens = 0
            output_tokens = 0
            if hasattr(response, 'usage_metadata'):
                input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0)
                output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0)

                self.logger.info(
                    f"📊 Token usage: {input_tokens} input + {output_tokens} output = "
                    f"{input_tokens + output_tokens} total tokens"
                )

            return response.text, input_tokens, output_tokens

        except Exception as e:
            self.logger.error(f"Error processing file {file_path} with Gemini: {e}")
            raise

    async def parse_with_images(self, file_path: str) -> tuple[str, int, int]:
        """
        Main orchestration method.

        Returns:
            Tuple[str, int, int]: (text, input_tokens, output_tokens)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_path = str(file_path)
        extension = self._get_file_extension(file_path)
        self.logger.info(f"Starting parsing for: {file_path}")

        try:
            if self._requires_conversion(file_path):
                self.logger.info(f"Converting {extension} file to text")
                if extension == ".docx":
                    # Conversion doesn't use Gemini, so 0 tokens
                    return self._convert_docx_to_text(file_path), 0, 0
                elif extension == ".doc":
                    return self._convert_doc_to_text(file_path), 0, 0

            elif self._is_supported_directly(file_path):
                mime_type = SUPPORTED_MIME_TYPES[extension]

                if extension == ".pdf":
                    images = self._extract_images_from_pdf(file_path)
                    image_descriptions = []
                    vision_input_tokens = 0
                    vision_output_tokens = 0

                    if images:
                        self.logger.info(f"Found {len(images)} images in PDF.")
                        for i, img in enumerate(images):
                            desc = await self._analyze_image_with_vision(img['data'], i)
                            image_descriptions.append(desc)
                            # Note: Vision API token tracking would need separate implementation

                    pdf_text, input_tokens, output_tokens = await self._process_with_gemini(
                        file_path, mime_type, "Extract all text content."
                    )
                    if image_descriptions:
                        pdf_text += "\n\n" + "\n".join(image_descriptions)
                    return pdf_text, input_tokens + vision_input_tokens, output_tokens + vision_output_tokens

                return await self._process_with_gemini(file_path, mime_type, "Extract all text content.")

            else:
                raise ValueError(f"Unsupported file type: {extension}")

        except Exception as e:
            self.logger.error(f"Error parsing document: {e}")
            raise

SUPPORTED_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/plain",
    ".html": "text/html",
    ".xml": "application/xml",
}

CONVERSION_REQUIRED = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
}