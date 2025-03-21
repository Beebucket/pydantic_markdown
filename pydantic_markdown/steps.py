import types
from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import Enum
from logging import getLogger
from typing import Any, Callable, Dict, Literal, Optional, Tuple, Type, Union, get_origin
from typing import get_args as get_generic_args
from warnings import warn

from anytree import PreOrderIter
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from pydantic_markdown.io import MarkdownWriter, get_header_reference
from pydantic_markdown.tree import PRIMITIVES, TypeNode

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


class CustomAnnotation(ABC):
    """This is the interface for non static custom type annotations.

    Inherit this and implement the magic functions to create a struct that you can annotate
    types with. That way, pydantic_markdown will be able to create markdown documentation for
    a given type.
    """

    @abstractmethod
    def __get_pydantic_reference__(self, references: TypeReferenceMap) -> str: ...

    @abstractmethod
    def __print_pydantic_markdown__(self, references: TypeReferenceMap, writer: MarkdownWriter) -> None: ...


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


class FieldInfoStep(Step):
    """This step represents how to document a pydantic FieldInfo.

    If no further metadata is present, it just forwards to the underlying annotations step implementation.
    """

    def __init__(self, type_hint: FieldInfo):
        super().__init__(type_hint)

        if type_hint.annotation is None:
            raise RuntimeError("Empty type annotation in type hint")

        self._reference_getter, self._printer = FieldInfoStep._get_interface_functions(type_hint)

    def get_reference(self, type_references: TypeReferenceMap) -> str:
        return self._reference_getter(type_references)

    def print(self, type_references: TypeReferenceMap, writer: MarkdownWriter) -> None:
        return self._printer(type_references, writer)

    @classmethod
    def covers(cls, type_hint: Any) -> bool:
        return isinstance(type_hint, FieldInfo)

    @staticmethod
    def _get_interface_functions(type_hint: FieldInfo) -> Tuple[ReferenceGetter, PrintFunction]:
        markdown_annotations = [
            annotation for annotation in type_hint.metadata if isinstance(annotation, CustomAnnotation)
        ]
        # No matching annotations, just use the underlying types implementation
        if len(markdown_annotations) == 0:
            inner_step = create_step(type_hint.annotation)
            return inner_step.get_reference, inner_step.print
        if len(markdown_annotations) != 1:
            raise RuntimeError("Too many pydantic markdown CustomAnnotations. You must only use one per type!")
        return markdown_annotations[0].__get_pydantic_reference__, markdown_annotations[0].__print_pydantic_markdown__


_POSSIBLE_STEPS = (
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


def create_steps(type_tree: TypeNode):
    """Creates a dictionary of steps for all types in given tree."""
    references: Dict[Any, Step] = dict()
    node: TypeNode
    for node in PreOrderIter(type_tree):
        if node.type_hint in references:
            continue
        references[node.type_hint] = create_step(node.type_hint)
    return references
