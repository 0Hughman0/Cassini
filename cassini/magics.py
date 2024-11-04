from warnings import warn

from IPython.core.magic import register_cell_magic
from IPython.core.interactiveshell import InteractiveShell
from IPython.display import Markdown, publish_display_data  # type: ignore[attr-defined]

from .environment import env
from .core import NotebookTierBase


def hlt(line: str, cell: str):
    """
    Highlight IPython cell magic. Captures the output of a cell and stores it in the [cassini.environment.env.o][cassini.environment._Env.o] highlights file.

    If the cell returns a string, this is used as a caption for the output.

    A title argument must be provided.
    """
    if env.is_shared(env):
        warn(
            "This notebook is in a shared context and therefore highlights magics won't work"
        )
        return cell

    if not isinstance(env.o, NotebookTierBase):
        raise ValueError(
            "Highlights can only be added to tiers that subclass NotebookTierBase"
        )

    if not line:
        raise ValueError("Please provide a title for the highlight")

    assert env.o

    outputs = []

    def capture_display(msg):
        if msg["content"]["data"] in outputs:  # display only once
            return None
        outputs.append(msg["content"])
        return msg

    cell = cell.strip()

    annotation = None

    if cell.endswith('"""'):
        *rest, annotation = cell.split('"""')[:-1]
        cell = '"""'.join(rest)

    shell = InteractiveShell.instance()
    # Capture any output that is displayed before output (like matplotlib plots)
    shell.display_pub.register_hook(capture_display)

    header = f"## {line}"

    try:
        publish_display_data({"text/markdown": header})

        result = shell.run_cell(cell).result

        if shell.display_formatter:
            outputs.append(
                dict(zip(("data", "metadata"), shell.display_formatter.format(result)))
            )

        if annotation:
            publish_display_data({"text/markdown": annotation})
    finally:
        shell.display_pub.unregister_hook(capture_display)

    all_out = outputs

    env.o.add_highlight(line, all_out)

    return None


def register():
    register_cell_magic(hlt)
