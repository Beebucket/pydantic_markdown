# Pydantic Markdown

Pydantic extension for generating markdown documentation of pydantic models.

It uses the information embedded in pydantic BaseModels to create a human readable
markdown documentation. The name, type and description of each model member get
documented.

## Command Line Interface

Here is how to use the command line interface:

```bash
# Install the tool
pip install https://github.com/Beebucket/pydantic_markdown

# Run the tool on the model "MyPydanticModel" from the package "MyPackage"
pydantic_markdown --model MyPackage.MyPydanticModel --output ./MyPydanticModel.md
```
# Configuration

Configuration of the pydantic_markdown tool.

| Name | Type | Required | Default | Description |
| -- | -- | -- | -- | -- |
| model | String | Yes |   | Complete identifier of the pydantic.BaseModel to document, including module. |
| output | File Path | No | .models.md | Path to store the markdown file in. Defaults to "./models.md" |

## Custom Type Annotations

The currently supported types are by no means complete. This repository shall only contain
pydantic and built in types. Never the less, there is a plugin interface through annotations.
That way non natively pydantic supported types can be made to support this library.

For overloading the recursion function of a type, just inherit the annotation interface and
annotate the type with it:

```python
from pydantic_markdown import CustomPrinterAnnotation, CustomReferenceAnnotation


class CustomIntAnnotation(CustomPrinterAnnotation, CustomReferenceAnnotation):
    def __get_pydantic_reference__(self, references: TypeReferenceMap) -> str:
        return "My annotated Number Type"

    def __print_pydantic_markdown__(self, references: TypeReferenceMap, writer: MarkdownWriter) -> None:
        writer.print_header(self.__get_pydantic_reference__(references), 0)
        writer.print_description(description="This is the very best custom annotated integer!")


AnnotatedInt = Annotated[int, CustomIntAnnotation()]
```

This way, the default implementation for documenting integers will be overwritten with the results from ```__get_pydantic_reference__``` and ```__print_pydantic_markdown__```.

## Annotating a class directly

In case you want to enable a self written class to support the markdown generation, you can just define the custom functions
as classmethods on the class itself:

```python
class ClassWithReferenceGetterAndPrinter(str):
    @classmethod
    def __get_pydantic_reference__(cls, reference_map):
        return TEST_REFERENCE

    @classmethod
    def __print_pydantic_markdown__(cls, references, writer) -> None:
        writer.write(TEST_PRINT_BODY)

```

# Developer Info

## Releasing

To create a release just push a tag following semantic versioning. The pipeline will then run all checks
and create a release draft if all checks succeed. You can then review that release.
