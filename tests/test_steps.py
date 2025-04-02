import io
from typing import Annotated

import pytest
from pydantic import AfterValidator

from pydantic_markdown.io import MarkdownWriter
from pydantic_markdown.steps import CustomPrinterAnnotation, CustomReferenceAnnotation, TypeReferenceMap, create_step

PLAIN_STRING_REFERENCE = "String"
TEST_REFERENCE = "test reference"
TEST_PRINT_BODY = "The very amazing markdown body."


class ReferenceGetterAnnotation(CustomReferenceAnnotation):
    def __get_pydantic_reference__(self, reference_map):
        return TEST_REFERENCE


class PrinterAnnotation(CustomPrinterAnnotation):
    def __print_pydantic_markdown__(self, references, writer) -> None:
        writer.write(TEST_PRINT_BODY)


PostValidatedString = Annotated[str, AfterValidator(lambda value: value)]
AnnotatedReferenceGetter = Annotated[str, ReferenceGetterAnnotation()]
AnnotatedPrinter = Annotated[str, PrinterAnnotation()]
AnnotatedReferenceAndPrinter = Annotated[str, ReferenceGetterAnnotation(), PrinterAnnotation()]


class ClassWithReferenceGetterAndPrinter(str):
    @classmethod
    def __get_pydantic_reference__(cls, reference_map):
        return TEST_REFERENCE

    @classmethod
    def __print_pydantic_markdown__(cls, references, writer) -> None:
        writer.write(TEST_PRINT_BODY)


@pytest.fixture
def reference_map():
    return TypeReferenceMap()


@pytest.fixture()
def string_buffer():
    with io.StringIO() as buffer:
        yield buffer


@pytest.fixture
def writer(string_buffer):
    return MarkdownWriter(string_buffer)


def test_annotated_after_validator_step(reference_map):
    step = create_step(PostValidatedString)
    assert step.get_reference(reference_map) == PLAIN_STRING_REFERENCE


def test_annotated_reference_getter(reference_map):
    step = create_step(AnnotatedReferenceGetter)
    assert step.get_reference(reference_map) == TEST_REFERENCE


def test_annotated_printer(reference_map, string_buffer, writer):
    step = create_step(AnnotatedPrinter)
    assert step.get_reference(reference_map) == PLAIN_STRING_REFERENCE
    step.print(reference_map, writer)
    assert string_buffer.getvalue() == TEST_PRINT_BODY


def test_annotated_reference_and_printer(reference_map, string_buffer, writer):
    step = create_step(AnnotatedReferenceAndPrinter)
    assert step.get_reference(reference_map) == TEST_REFERENCE
    step.print(reference_map, writer)
    assert string_buffer.getvalue() == TEST_PRINT_BODY


def test_custom_class(reference_map, string_buffer, writer):
    step = create_step(ClassWithReferenceGetterAndPrinter)
    assert step.get_reference(reference_map) == TEST_REFERENCE
    step.print(reference_map, writer)
    assert string_buffer.getvalue() == TEST_PRINT_BODY
