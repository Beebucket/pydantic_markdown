from typing import List

from anytree import PreOrderIter
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pytest import raises

from pydantic_markdown.tree import create_type_tree


class DummyRoot(BaseModel):
    number: int
    list: List[str]


class RecursiveModel(BaseModel):
    recursive: "RecursiveModel"


def test_left_to_right():
    root_node = create_type_tree(DummyRoot)
    assert len(root_node.children) == 2
    pre_order_nodes = list(PreOrderIter(root_node))
    assert len(pre_order_nodes) == 4
    assert pre_order_nodes[0].type_hint is DummyRoot
    assert isinstance(pre_order_nodes[1].type_hint, FieldInfo)
    assert pre_order_nodes[1].type_hint.annotation is int
    assert isinstance(pre_order_nodes[2].type_hint, FieldInfo)
    assert pre_order_nodes[2].type_hint.annotation is List[str]
    assert pre_order_nodes[3].type_hint is str


def test_recursive_raises():
    """Test that recursive models raise an error instead of running endlessly."""
    with raises(NotImplementedError):
        create_type_tree(RecursiveModel)
