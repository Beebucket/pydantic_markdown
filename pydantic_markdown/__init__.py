from packaging.version import Version

from pydantic_markdown.io import MarkdownWriter as MarkdownWriter
from pydantic_markdown.steps import CustomAnnotatedClass as CustomAnnotatedClass
from pydantic_markdown.steps import CustomPrinterAnnotation as CustomPrinterAnnotation
from pydantic_markdown.steps import CustomReferenceAnnotation as CustomReferenceAnnotation
from pydantic_markdown.steps import TypeReferenceMap as TypeReferenceMap
from pydantic_markdown.writer import document_model as document_model

try:
    from ._version import __version__
except ImportError:
    __version__ = "0.0.0+dirty"


CURRENT_VERSION = Version(__version__)
