from datetime import datetime, timedelta
from enum import Enum
from logging import getLogger
from pathlib import Path
from typing import (
    Any,
    Iterator,
    Literal,
    Optional,
    Type,
    cast,
    get_origin,
)
from typing import (
    get_args as get_generic_args,
)
from warnings import warn

from anytree import Node
from pydantic import AnyUrl, BaseModel
from pydantic.fields import FieldInfo

PRIMITIVES = {
    str: "String",
    int: "Integer",
    None: "None/Null",
    type(None): "None/Null",
    float: "Floating Point Number",
    bool: "Boolean",
    Path: "File Path",
    datetime: "ISO8601 Datetime",
    timedelta: "ISO8601 Duration",
    AnyUrl: "URL",
}

_logger = getLogger(__name__)


class NotImplementedWarning(RuntimeWarning):
    pass


class TypeNode(Node):
    type_hint: Any

    def __init__(self, type_hint: Any, name: Optional[str] = None, parent=None, children=None, **kwargs):
        if name is None:
            name = str(object=type_hint)
        super().__init__(name=name, type_hint=type_hint, parent=parent, children=children, **kwargs)


def create_type_tree(root_type_hint: Any, parent: Optional[TypeNode] = None) -> TypeNode:
    _logger.debug("Starting to traverse %s", root_type_hint)
    root_node = TypeNode(parent=parent, type_hint=root_type_hint)
    for child_type_hint in _get_children(root_type_hint):
        if any(node.type_hint == child_type_hint for node in root_node.iter_path_reverse()):
            raise NotImplementedError(f'The annotation "{child_type_hint}" is recursive. This is not yet supported!')
        create_type_tree(child_type_hint, root_node)
    return root_node


def _get_children(type_to_traverse: Any) -> Iterator:
    if type_to_traverse in PRIMITIVES:
        return

    if isinstance(type_to_traverse, FieldInfo):
        if type_to_traverse.annotation is None:
            message = f'FieldInfo annotation "{type_to_traverse}" is empty'
            warn(message, RuntimeWarning)
            _logger.warning(message)
        yield from _get_children(type_to_traverse.annotation)
        return

    if isinstance(type_to_traverse, type):
        if issubclass(type_to_traverse, Enum):
            return
        if issubclass(type_to_traverse, BaseModel):
            safe_model_type = cast(Type[BaseModel], type_to_traverse)
            yield from (field_info for field_info in safe_model_type.model_fields.values())
            return

    origin = get_origin(type_to_traverse)
    if origin is not None:
        if origin is Literal:
            return
        # Generic
        yield from get_generic_args(type_to_traverse)
        return

    message = f'No implementation for walking "{type_to_traverse}"'
    warn(message, NotImplementedWarning)
    _logger.warning(message)
