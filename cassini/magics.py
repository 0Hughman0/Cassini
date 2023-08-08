from IPython.core.magic import register_cell_magic
from IPython.core.interactiveshell import InteractiveShell
from IPython.display import Markdown, publish_display_data

from .environment import env


def hlt(line, cell):
    if not line:
        raise ValueError("Please provide a title for the highlight")
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


def cache(line, cell):
    key = str(hash(cell.strip()))
    cache = env.o.get_cached().get(key)

    if cache:
        print(f"Using cached version ('{key}')")
        for output in cache:
            publish_display_data(**output)
        return None

    outputs = []

    def capture_display(msg):
        if msg["content"]["data"] in outputs:  # display only once
            return None
        outputs.append(msg["content"])
        return msg

    shell = InteractiveShell.instance()
    # Capture any output that is displayed before output (like matplotlib plots)
    shell.display_pub.register_hook(capture_display)

    try:
        output = shell.run_cell(cell)
        result = output.result
        if output.error_in_exec:
            raise RuntimeError("Error in cell output, not caching")
        outputs.append(
            dict(zip(("data", "metadata"), shell.display_formatter.format(result)))
        )
    finally:
        shell.display_pub.unregister_hook(capture_display)

    all_out = outputs

    env.o.cache_result(key, all_out)

    return None


def conc(line, cell):
    if env.o.conclusion and line != "force":
        raise RuntimeError(
            f"Conclusion for {env.o} already set, use %%conc force to force update"
        )
    env.o.conclusion = cell
    return Markdown(cell)


def register():
    register_cell_magic(hlt)
    register_cell_magic(cache)
    register_cell_magic(conc)
