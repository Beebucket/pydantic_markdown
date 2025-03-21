from io import TextIOBase
from typing import Iterable, Iterator, List


def get_header_reference(header_text: str) -> str:
    """Returns a reference to the header with the given name."""
    return f"[{header_text}](#{header_text})"


class MarkdownWriter:
    def __init__(self, text_io: TextIOBase):
        self._text_io = text_io

    def write(self, text: str) -> None:
        self._text_io.write(text)

    def print_table(self, headers: List[str], rows: Iterator[Iterator[str]]) -> None:
        column_count = len(headers)
        self._print_table_row(headers)
        self._print_table_row("--" for _ in range(column_count))
        for row in rows:
            row_elements = list(row)
            if len(row_elements) != column_count:
                raise RuntimeError("Failed to put row into table, it has the wrong number of entries!")
            self._print_table_row(row_elements)
        self._text_io.write("\n\n")

    def print_header(self, text: str, level: int):
        self._text_io.write("#" * (1 + level) + f" {text}\n\n")

    def print_description(self, description: str) -> None:
        for line in description.splitlines(keepends=False):
            self._text_io.write(line.strip() + "\n")
        self._text_io.write("\n")

    def _print_table_row(self, row: Iterable[str]) -> None:
        self._text_io.write("| " + " | ".join(row) + " |\n")
