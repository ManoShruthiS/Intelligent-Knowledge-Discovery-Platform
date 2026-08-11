import io
import fitz  # PyMuPDF
from docx import Document

class UnsupportedFileTypeError(Exception):
    """Exception raised for unsupported file types."""
    pass

class DocumentProcessingError(Exception):
    """Exception raised for errors during document extraction."""
    pass

def process_document(file_content: bytes, filename: str) -> dict:
    """
    Main entry point for extracting text from a document.
    Dispatches to the correct extractor based on the filename extension.
    Returns metadata, the full text, and a list of page objects.
    """
    if not file_content:
        raise DocumentProcessingError("File is empty.")

    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    
    file_type = ""
    pages = []
    
    try:
        if ext == 'pdf':
            file_type = "PDF"
            pages = _extract_pdf(file_content)
        elif ext == 'docx':
            file_type = "DOCX"
            pages = _extract_docx(file_content)
        elif ext == 'txt':
            file_type = "TXT"
            pages = _extract_txt(file_content)
        else:
            raise UnsupportedFileTypeError(f"Unsupported file type: {ext}")
            
    except UnsupportedFileTypeError:
        raise
    except Exception as e:
        raise DocumentProcessingError(f"Failed to extract text: {str(e)}")
        
    full_text = "\n".join(page['text'] for page in pages if page['text'])
    page_count = len(pages) if file_type == "PDF" else None

    return {
        "filename": filename,
        "file_type": file_type,
        "file_size": len(file_content),
        "page_count": page_count,
        "character_count": len(full_text),
        "text": full_text,
        "pages": pages
    }

def _extract_pdf(file_content: bytes) -> list[dict]:
    """Extracts text from a PDF file page by page."""
    pages = []
    try:
        # Open the PDF from bytes
        doc = fitz.open(stream=file_content, filetype="pdf")
        page_count = len(doc)
        
        for page_num in range(page_count):
            page = doc.load_page(page_num)
            page_text = page.get_text()
            if page_text:
                # 1-indexed page numbers for human readability
                pages.append({"page_number": page_num + 1, "text": page_text})
                
        doc.close()
        return pages
    except Exception as e:
        raise Exception(f"PDF processing error: {str(e)}")

def _extract_docx(file_content: bytes) -> list[dict]:
    """Extracts text from a DOCX file."""
    try:
        doc = Document(io.BytesIO(file_content))
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return [{"page_number": None, "text": "\n".join(paragraphs)}]
    except Exception as e:
        raise Exception(f"DOCX processing error: {str(e)}")

def _extract_txt(file_content: bytes) -> list[dict]:
    """Extracts text from a TXT file handling common encodings."""
    encodings = ['utf-8', 'latin-1', 'windows-1252']
    
    for enc in encodings:
        try:
            text = file_content.decode(enc)
            return [{"page_number": None, "text": text}]
        except UnicodeDecodeError:
            continue
            
    raise Exception("Unable to decode text file with standard encodings.")
