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

# Developer Info

## Releasing

To create a release just push a tag following semantic versioning. The pipeline will then run all checks
and create a release draft if all checks succeed. You can then review that release.
