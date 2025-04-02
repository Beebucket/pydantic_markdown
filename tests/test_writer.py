from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from subprocess import PIPE, run
from typing import Annotated, Dict, List, Literal, Mapping, Optional, Set, Tuple, Type

from pydantic import AfterValidator, AnyUrl, BaseModel, Field
from pytest import fixture, raises, warns

from pydantic_markdown import document_model
from pydantic_markdown.io import MarkdownWriter
from pydantic_markdown.steps import (
    ClassDocstringMissingWarning,
    CustomPrinterAnnotation,
    CustomReferenceAnnotation,
    FieldDescriptionMissingWarning,
    TypeReferenceMap,
)
from pydantic_markdown.writer import Configuration, _import_class


class IntEnumeration(Enum):
    """My integer enumeration"""

    Zero = 0
    One = 1
    Two = 2


class StringEnumeration(str, Enum):
    """My string enumeration"""

    One = "One"
    Two = "Two"
    Three = "Three"


PostValidatedString = Annotated[str, AfterValidator(lambda value: value)]


class CompleteClass(BaseModel):
    """This is my very well documented class"""

    number: int = Field(description="A number")
    name: str = Field(description="Some random name")
    dictionary: Dict[str, int] = Field(description="Some string to integer dictionary")
    mapping: Mapping[int, str] = Field(description="I can also map int to string")
    list: List[int] = Field(description="My beautiful integer list")
    set: Set[str] = Field(description="The best set of strings")
    optional: Optional[int] = Field(description="This int can also not be there")
    tuple: Tuple[int, str] = Field(description="This tuple contains a int and a string")
    literal: Literal["one", "two", "three"] = Field(description="One of the given literal values")
    numeric_enumeration: IntEnumeration = Field(description="The numeric enumeration")
    string_enumeration: StringEnumeration = Field(description="String enumeration")
    path: Path = Field(description="The path to the end of the rainbow")
    time_span: timedelta = Field(description="A duration")
    url: AnyUrl = Field(description="This should be any kind of URL")
    date: datetime = Field(description="You can store datetimes in here")
    post_validated_string: PostValidatedString = Field(description="String with post validator")


class ModelWithoutDocstring(BaseModel):
    pass


class ModelWithUndescribedMembers(BaseModel):
    """I have a model comment, but no member description"""

    string: str


class EnumMissingDocstring(Enum):
    zero = 0
    one = 1


class ModelMissingEnumDocstring(BaseModel):
    """I have a docstring, my enumeration type does not!"""

    enum: EnumMissingDocstring = Field(description="Enumeration which is not documented")


@fixture
def output_io(output_dir):
    with open(output_dir / "models.md", "at", encoding="utf-8") as file:
        yield file


class CustomIntAnnotation(CustomPrinterAnnotation, CustomReferenceAnnotation):
    def __get_pydantic_reference__(self, references: TypeReferenceMap) -> str:
        return "My annotated Number Type"

    def __print_pydantic_markdown__(self, references: TypeReferenceMap, writer: MarkdownWriter) -> None:
        writer.print_header(self.__get_pydantic_reference__(references), 0)
        writer.print_description(description="This is the very best custom annotated integer!")


AnnotatedInt = Annotated[int, CustomIntAnnotation()]


class ModelWithAnnotatedInt(BaseModel):
    """This model has a custom annotated int."""

    annotated_int: AnnotatedInt = Field(description="I am an annotated int.")


def test_import_class():
    hopefully_path_class = _import_class(_get_id(Path))
    assert hopefully_path_class is Path


def test_import_non_existing_module():
    with raises(ImportError):
        _import_class("NonExistingModule.Class")


def test_import_non_existing_class():
    with raises(ImportError):
        _import_class("pydantic_markdown.NonExistingClass")


def test_missing_enum_docstring(output_io):
    with warns(ClassDocstringMissingWarning):
        document_model(output_io, ModelMissingEnumDocstring)


def test_missing_field_description(output_io):
    with warns(FieldDescriptionMissingWarning):
        document_model(output_io, ModelWithUndescribedMembers)


def test_document_model(output_io):
    document_model(output_io, CompleteClass)


def test_incomplete_model_raises(output_io):
    with warns(ClassDocstringMissingWarning):
        document_model(output_io, ModelWithoutDocstring)


def test_incomplete_model_without_strict(output_io):
    with warns(ClassDocstringMissingWarning):
        document_model(output_io, ModelWithoutDocstring)


def test_custom_pydantic_annotated(output_io):
    document_model(output_io, ModelWithAnnotatedInt)


def test_cli(output_dir):
    completed_process = run(
        ["pydantic_markdown", "--model", _get_id(Configuration), "--output", output_dir],
        check=False,
        stderr=PIPE,
    )
    assert completed_process.returncode == 0, completed_process.stderr.decode()


def _get_id(model: Type) -> str:
    return f"{model.__module__}.{model.__qualname__}"
