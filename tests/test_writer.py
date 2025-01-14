from datetime import timedelta
from enum import Enum
from pathlib import Path
from subprocess import PIPE, run
from typing import Dict, List, Literal, Mapping, Optional, Set, Tuple, Type

from pydantic import AnyUrl, BaseModel, Field
from pytest import raises, warns

from pydantic_markdown.steps import ClassDocstringMissingWarning, FieldDescriptionMissingWarning
from pydantic_markdown.writer import Configuration, _document_model, _import_class


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


def test_import_class():
    hopefully_path_class = _import_class(_get_id(Path))
    assert hopefully_path_class is Path


def test_import_non_existing_module():
    with raises(ImportError):
        _import_class("NonExistingModule.Class")


def test_import_non_existing_class():
    with raises(ImportError):
        _import_class("pydantic_markdown.NonExistingClass")


def test_missing_enum_docstring(output_dir):
    config = Configuration(model=_get_id(ModelMissingEnumDocstring), output=output_dir)
    with warns(ClassDocstringMissingWarning):
        _document_model(config)


def test_missing_field_description(output_dir):
    config = Configuration(model=_get_id(ModelWithUndescribedMembers), output=output_dir)
    with warns(FieldDescriptionMissingWarning):
        _document_model(config)


def test_document_model(output_dir):
    config = Configuration(
        model=_get_id(CompleteClass),
        output=output_dir / "models.md",
    )
    _document_model(config)


def test_incomplete_model_raises(output_dir):
    config = Configuration(
        model=_get_id(ModelWithoutDocstring),
        output=output_dir,
    )
    with warns(ClassDocstringMissingWarning):
        _document_model(config)


def test_incomplete_model_without_strict(output_dir):
    config = Configuration(
        model=_get_id(ModelWithoutDocstring),
        output=output_dir,
    )
    with warns(ClassDocstringMissingWarning):
        _document_model(config)


def test_cli(output_dir):
    completed_process = run(
        ["pydantic_markdown", "--model", _get_id(Configuration), "--output", output_dir],
        check=False,
        stderr=PIPE,
    )
    assert completed_process.returncode == 0, completed_process.stderr.decode()


def _get_id(model: Type) -> str:
    return f"{model.__module__}.{model.__qualname__}"
