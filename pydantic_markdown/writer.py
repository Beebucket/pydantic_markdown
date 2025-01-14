from importlib import import_module
from io import StringIO, TextIOWrapper
from logging import getLogger
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Set, Type, Union

from anytree import PostOrderIter, PreOrderIter
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic_markdown.io import MarkdownWriter
from pydantic_markdown.steps import MissingReferenceError, Step, TypeReferenceMap, create_step
from pydantic_markdown.tree import TypeNode

_logger = getLogger(__name__)


class Configuration(BaseSettings):
    """Configuration of the pydantic_markdown tool."""

    model: str = Field(description="Complete identifier of the pydantic.BaseModel to document, including module.")
    output: Path = Field(
        default=Path(".models.md"), description='Path to store the markdown file in. Defaults to "./models.md"'
    )


class CliConfig(Configuration):
    model_config = SettingsConfigDict(cli_parse_args=True)


def _import_class(path: str) -> Any:
    components = path.rsplit(".", 1)
    module: Union[ModuleType, Type] = import_module(components[0])
    try:
        class_to_import = getattr(module, components[1])
    except AttributeError:
        _logger.error(
            '"%s" not in %s. The following attributes are available:\n\t%s',
            components[1],
            module,
            "\n\t".join(module.__dict__),
        )
    return class_to_import


class Writer:
    def __init__(self, text_io: TextIOWrapper, type_hint: Any):
        self._already_printed: Set[Any] = set()
        self._io = text_io
        self._steps: Dict[Any, Step] = {type_hint: create_step(type_hint)}
        self._references = TypeReferenceMap()
        self._dependencies = TypeNode(type_hint)

    def write(self) -> None:
        all_succeeded = False
        while not all_succeeded:
            if not self._create_all_references():
                continue
            if not self._print_all():
                continue
            all_succeeded = True

    def _create_all_references(self) -> bool:
        for node in PostOrderIter(self._dependencies):
            if node.type_hint in self._references:
                continue
            step = self._steps.get(node.type_hint)
            if step is None:
                step = create_step(node.type_hint)
                self._steps[node.type_hint] = step
            try:
                self._references[node.type_hint] = step.get_reference(self._references)
            except MissingReferenceError as error:
                TypeNode(error.type_hint, parent=node)
                return False
        return True

    def _print_all(self) -> bool:
        for node in PreOrderIter(self._dependencies):
            if node.type_hint in self._already_printed:
                continue

            try:
                text_buffer = StringIO()
                buffered_markdown_io = MarkdownWriter(text_buffer)
                self._steps[node.type_hint].print(self._references, buffered_markdown_io)
                self._io.write(text_buffer.getvalue())
                self._already_printed.add(node.type_hint)
            except MissingReferenceError as error:
                TypeNode(error.type_hint, parent=node)
                return False
            finally:
                text_buffer.close()
        return True


def _document_model(config: Configuration):
    if config.output.is_dir():
        config.output /= "models.md"

    root_type = _import_class(config.model)
    with open(config.output, "wt", encoding="utf-8") as file:
        writer = Writer(file, root_type)
        writer.write()


def main():
    _document_model(CliConfig())


if __name__ == "__main__":
    main()
