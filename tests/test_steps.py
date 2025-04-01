from typing import Annotated

from pydantic import AfterValidator

from pydantic_markdown.steps import create_step

PostValidatedString = Annotated[str, AfterValidator(lambda value: value)]


def test_annotated_after_validator_step():
    create_step(PostValidatedString)
