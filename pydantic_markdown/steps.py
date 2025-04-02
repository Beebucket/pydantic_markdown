import types
from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import Enum
from logging import getLogger
from typing import Annotated, Any, Callable, Generic, List, Literal, Optional, Type, TypeVar, Union, get_origin
from typing import get_args as get_generic_args
from warnings import warn

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from pydantic_markdown.io import MarkdownWriter, get_header_reference
from pydantic_markdown.tree import PRIMITIVES

_logger = getLogger(__name__)


class IncompleteDocumentationWarning(RuntimeWarning):
    pass


class ClassDocstringMissingWarning(IncompleteDocumentationWarning):
    pass


class FieldDescriptionMissingWarning(IncompleteDocumentationWarning):
    pass


class IncompleteTypeAnnotationsWarning(RuntimeWarning):
    pass


class NotImplementedWarning(RuntimeWarning):
    pass


class MissingReferenceError(KeyError):
    def __init__(self, type_hint: Any):
        super().__init__(f'Missing reference to "{_get_type_hint_description(type_hint)}"')
        self.type_hint = type_hint


class TypeReferenceMap(dict):
    """
    Raises:
        MissingReferenceError if the requested type_hint is not yet registered. That will then be handled by
                              the caller to build a dependency tree and executing the functions in the
                              proper order.
    """

    def __missing__(self, type_hint):
        raise MissingReferenceError(type_hint)


class CustomReferenceAnnotation(ABC):
    """
    This is the interface for getting the reference to a given class.

    You can inherit this from either the class you want to customize or an annotation.
    """

    @abstractmethod
    def __get_pydantic_reference__(self, references: TypeReferenceMap) -> str:
        """
        Returns a reference to the annotated type.

        Can be either a short name describing the type or a full on header of the documentation printed by the print function.
        """
        ...


class CustomPrinterAnnotation(ABC):
    """
    This is the interface for custom type printouts in the markdown.

    You can inherit this from either the class you want to customize, or an annotation.
    """

    @abstractmethod
    def __print_pydantic_markdown__(self, references: TypeReferenceMap, writer: MarkdownWriter) -> None:
        """
        Prints the body of the type description.

        This can do either nothing, in which case there will not be a text body dedicated to
        further elaborate the type. Or it prints the header and body of the detailed explanation
        of this type.
        """
        ...


class CustomAnnotatedClass(CustomReferenceAnnotation, CustomPrinterAnnotation):
    pass


class Step(ABC):
    def __init__(self, type_hint: Any) -> None:
        self._type = type_hint

    @property
    def type(self) -> Any:
        return self._type

    @abstractmethod
    def get_reference(self, type_references: TypeReferenceMap) -> str: ...

    @abstractmethod
    def print(self, type_references: TypeReferenceMap, writer: MarkdownWriter) -> None: ...

    @classmethod
    @abstractmethod
    def covers(cls, type_hint: Any) -> bool: ...


class PrimitiveStep(Step):
    def __init__(self, primitive_type: Type):
        super().__init__(primitive_type)
        self._primitive_type = primitive_type

    def get_reference(self, _):
        return PRIMITIVES[self._primitive_type]

    def print(self, type_references, writer) -> None:
        pass

    @classmethod
    def covers(cls, type_hint):
        return type_hint in PRIMITIVES


class EnumStep(Step):
    # This class solely exists to get the docstring of an undocumented enumeration.
    class _DummyEnum(Enum):
        pass

    def __init__(self, enum_type: Type[Enum]):
        super().__init__(enum_type)
        self._enum_type = enum_type

    def get_reference(self, _):
        return get_header_reference(self._enum_type.__name__)

    def print(self, type_references: TypeReferenceMap, writer: MarkdownWriter) -> None:
        writer.print_header(self._enum_type.__name__, 0)

        if (self._enum_type.__doc__ is not None) and (self._enum_type.__doc__ != EnumStep._DummyEnum.__doc__):
            writer.print_description(self._enum_type.__doc__)
        else:
            message = f'Enumeration "{self._enum_type}" is missing a docstring'
            warn(message, ClassDocstringMissingWarning)
            _logger.warning(message)

        writer.write("Possible values:\n")
        for value in self._enum_type:
            if isinstance(value.value, str):
                writer.write(f'* "{value.value}"\n')
            else:
                writer.write(f"* {value.value}\n")
        writer.write("\n\n")

    @classmethod
    def covers(cls, type_hint):
        return isinstance(type_hint, type) and issubclass(type_hint, Enum)


class ModelStep(Step):
    def __init__(self, pydantic_model: Type[BaseModel]):
        super().__init__(pydantic_model)
        self._model = pydantic_model

    def get_reference(self, _) -> str:
        return get_header_reference(self._model.__name__)

    def print(self, type_references, writer) -> None:
        writer.print_header(self._model.__name__, 0)

        if (self._model.__doc__ is not None) and (self._model.__doc__ != BaseModel.__doc__):
            writer.print_description(self._model.__doc__)
        else:
            message = f'BaseModel "{self._model}" is missing a docstring!'
            warn(message, ClassDocstringMissingWarning)
            _logger.warning(message)

        field_iterator = (
            self._get_pydantic_field_entries(name, field, type_references)
            for name, field in self._model.model_fields.items()
        )
        writer.print_table(["Name", "Type", "Required", "Default", "Description"], field_iterator)

    @classmethod
    def covers(cls, type_hint):
        return isinstance(type_hint, type) and issubclass(type_hint, BaseModel)

    def _get_pydantic_field_entries(self, name: str, field_info: FieldInfo, type_references: TypeReferenceMap):
        yield name

        if field_info.annotation is not None:
            yield type_references[field_info]
        else:
            message = f'Field "{name}" does not have any type annotation.'
            warn(message, IncompleteTypeAnnotationsWarning)
            _logger.warning(message)
            yield "unknown"

        yield "Yes" if field_info.is_required() else "No"

        if field_info.default and (field_info.default is not PydanticUndefined):
            yield f"{field_info.default}"
        elif field_info.default_factory and (field_info.default_factory is not PydanticUndefined):
            yield f"{field_info.default_factory()}"
        else:
            yield " "

        if field_info.description:
            yield f"{field_info.description}"
        else:
            message = f'Field "{name}" does not have a description. This is required in strict mode.'
            warn(message, FieldDescriptionMissingWarning)
            _logger.warning(message)
            yield " "


class GenericStep(Step):
    def __init__(self, generic: Any):
        super().__init__(generic)
        self._origin = get_origin(generic)
        self._type = generic
        self._generic_args = get_generic_args(generic)

    def print(self, type_references, writer):
        pass

    @staticmethod
    def _warn_generic_arguments(message: str):
        warn(message, IncompleteTypeAnnotationsWarning)
        _logger.warning(message)


class ListStep(GenericStep):
    def __init__(self, type_hint):
        super().__init__(type_hint)
        if len(self._generic_args) != 1:
            GenericStep._warn_generic_arguments(f"Excepted one generic argument for list, got {self._generic_args}")

    def get_reference(self, type_references: TypeReferenceMap) -> str:
        if len(self._generic_args) > 0:
            return f"List of {type_references[self._generic_args[0]]}"
        else:
            return "List"

    @classmethod
    def covers(cls, type_hint):
        return get_origin(type_hint) is list


class SetStep(GenericStep):
    def __init__(self, generic):
        super().__init__(generic)

        if len(self._generic_args) != 1:
            GenericStep._warn_generic_arguments(f"Expected one generic argument for sets, got {self._generic_args}")

    def get_reference(self, type_references):
        if len(self._generic_args) > 0:
            return f"Set of {type_references[self._generic_args[0]]}"
        else:
            return "Set"

    @classmethod
    def covers(cls, type_hint):
        return get_origin(type_hint) is set


class MappingStep(GenericStep):
    def __init__(self, generic):
        super().__init__(generic)

        if len(self._generic_args) != 2:
            GenericStep._warn_generic_arguments(
                f'Expected mapping to have two template parameter. Got these: "{self._generic_args}"'
            )

    def get_reference(self, type_references):
        if len(self._generic_args) >= 2:
            return f"Mapping of {type_references[self._generic_args[0]]} to {type_references[self._generic_args[1]]}"
        else:
            return "Mapping"

    @classmethod
    def covers(cls, type_hint):
        origin = get_origin(type_hint)
        return (origin is dict) or (origin is Mapping)


class UnionStep(GenericStep):
    def get_reference(self, type_references):
        return " or ".join(type_references[arg] for arg in self._generic_args)

    @classmethod
    def covers(cls, type_hint):
        origin = get_origin(type_hint)
        return (origin is Union) or (origin is Optional) or (origin is types.UnionType)


class TupleStep(GenericStep):
    def get_reference(self, type_references):
        return "Tuple of " + " and ".join(type_references[arg] for arg in self._generic_args)

    @classmethod
    def covers(cls, type_hint):
        return get_origin(type_hint) is tuple


class LiteralStep(GenericStep):
    def get_reference(self, type_references):
        return "Either " + " or ".join(f'"{arg}"' if isinstance(arg, str) else arg for arg in self._generic_args)

    @classmethod
    def covers(cls, type_hint):
        return get_origin(type_hint) is Literal


ReferenceGetter = Callable[[TypeReferenceMap], str]
PrintFunction = Callable[[TypeReferenceMap, MarkdownWriter], None]


def _get_property_from_annotations(property_name: str, annotations: List[Any]):
    reference_getter = None

    for annotation in annotations:
        annotation_reference_getter = getattr(annotation, property_name, None)
        if annotation_reference_getter:
            if reference_getter:
                raise RuntimeError(f'Multiple annotations found for "{property_name}"! Only one is valid!')
            reference_getter = annotation_reference_getter

    return reference_getter


def _get_reference_getter(type_hint: Any, annotations: List[Any]) -> ReferenceGetter:
    reference_getter = _get_property_from_annotations(
        CustomReferenceAnnotation.__get_pydantic_reference__.__name__, annotations
    )
    if reference_getter:
        return reference_getter

    # None was annotated. Fall back to type hint implementation
    return create_step(type_hint).get_reference


def _get_printer(type_hint: Any, annotations: List[Any]) -> PrintFunction:
    printer = _get_property_from_annotations(CustomPrinterAnnotation.__print_pydantic_markdown__.__name__, annotations)
    if printer:
        return printer

    # None was annotated. Fall back to type hint implementation
    return create_step(type_hint).print


_AnnotatedType = TypeVar("_AnnotatedType")
_Annotations = TypeVar("_Annotations")


class AnnotatedStep(Generic[_AnnotatedType, _Annotations], Step):
    def __init__(self, type_hint: Annotated[_AnnotatedType, _Annotations]):
        super().__init__(type_hint)
        origin: _AnnotatedType
        origin, *annotations = get_generic_args(type_hint)
        self._reference_getter = _get_reference_getter(origin, annotations)
        self._printer = _get_printer(origin, annotations)

    def get_reference(self, type_references):
        return self._reference_getter(type_references)

    def print(self, type_references, writer):
        return self._printer(type_references, writer)

    @classmethod
    def covers(cls, type_hint: Any) -> bool:
        origin = get_origin(type_hint)
        return origin is Annotated


class FieldInfoStep(Step):
    """This step represents how to document a pydantic FieldInfo.

    If no further metadata is present, it just forwards to the underlying annotations step implementation.
    """

    def __init__(self, type_hint: FieldInfo):
        super().__init__(type_hint)

        if type_hint.annotation is None:
            raise RuntimeError("Empty type annotation in type hint")

        self._reference_getter = _get_reference_getter(type_hint.annotation, type_hint.metadata)
        self._printer = _get_printer(type_hint.annotation, type_hint.metadata)

    def get_reference(self, type_references: TypeReferenceMap) -> str:
        return self._reference_getter(type_references)

    def print(self, type_references: TypeReferenceMap, writer: MarkdownWriter) -> None:
        return self._printer(type_references, writer)

    @classmethod
    def covers(cls, type_hint: Any) -> bool:
        return isinstance(type_hint, FieldInfo)


class CustomClassStep(Step):
    """This step represents how to document a pydantic FieldInfo.

    If no further metadata is present, it just forwards to the underlying annotations step implementation.
    """

    _ERROR_MESSAGE_NEED_BOTH = "When custom annotating classes for pydantic markdown, always specify the reference getter AND printer function!"

    def __init__(self, type_hint: CustomAnnotatedClass):
        reference_getter = getattr(type_hint, CustomReferenceAnnotation.__get_pydantic_reference__.__name__, None)
        if not reference_getter:
            raise RuntimeError(CustomClassStep._ERROR_MESSAGE_NEED_BOTH)
        self._reference_getter = reference_getter

        printer = getattr(type_hint, CustomPrinterAnnotation.__print_pydantic_markdown__.__name__, None)
        if not printer:
            raise RuntimeError(CustomClassStep._ERROR_MESSAGE_NEED_BOTH)
        self._printer = printer

    def get_reference(self, type_references: TypeReferenceMap) -> str:
        return self._reference_getter(type_references)

    def print(self, type_references: TypeReferenceMap, writer: MarkdownWriter) -> None:
        self._printer(type_references, writer)

    @classmethod
    def covers(cls, type_hint: Any) -> bool:
        has_reference_getter = (
            getattr(type_hint, CustomReferenceAnnotation.__get_pydantic_reference__.__name__, None) is not None
        )
        has_printer = getattr(type_hint, CustomPrinterAnnotation.__print_pydantic_markdown__.__name__, None) is not None
        return has_reference_getter or has_printer


_POSSIBLE_STEPS = (
    AnnotatedStep,
    CustomClassStep,
    PrimitiveStep,
    EnumStep,
    ModelStep,
    ListStep,
    SetStep,
    MappingStep,
    UnionStep,
    TupleStep,
    LiteralStep,
    FieldInfoStep,
)


def create_step(type_hint: Any) -> Step:
    for step in _POSSIBLE_STEPS:
        if step.covers(type_hint):
            return step(type_hint)
    name = _get_type_hint_description(type_hint)
    raise NotImplementedError(f'Implementation does not yet support "{name}"')


def _get_type_hint_description(type_hint):
    name = f"{type_hint}" if isinstance(type_hint, type) else f"{type(type_hint)}: {type_hint}"
    return name
