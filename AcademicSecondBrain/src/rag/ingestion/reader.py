from pathlib import Path
from typing import List, Union
from llama_index.core.readers import SimpleDirectoryReader
from llama_index.readers.file import PyMuPDFReader, DocxReader, ImageReader, PptxReader
from llama_index.core import Document

def get_file_extractors() -> dict:
    return {
        ".pdf": PyMuPDFReader(),
        ".docx": DocxReader(),
        ".doc": DocxReader(),
        ".jpg": ImageReader(),
        ".png": ImageReader(),
        ".jpeg": ImageReader(),
        ".pptx": PptxReader(),
    }

def load_documents_from_path(path: Union[str, Path, List[Union[str, Path]]]) -> List[Document]:
    """Loads documents purely for runtime extraction. No deduplication logic."""
    extractors = get_file_extractors()

    if isinstance(path, list):
        input_files = [str(p) for p in path]
        document = SimpleDirectoryReader(
            input_files=input_files,
            file_extractor=extractors,
            filename_as_id=True
        )
    else:
        document = SimpleDirectoryReader(
            input_dir=str(path),
            file_extractor=extractors,
            filename_as_id=True
        )

    return document.load_data()