"""Generate the code reference pages."""

from pathlib import Path

import mkdocs_gen_files

root = Path(__file__).parent.parent
src = root / "cassini" 

nav = mkdocs_gen_files.Nav()

for path in sorted(src.rglob("*.py")):
    path = Path('cassini') / path  
    module_path = Path('cassini') / path.relative_to(src).with_suffix("")  
    doc_path = path.relative_to(src).with_suffix(".md")  
    full_doc_path = Path("api", doc_path)  

    parts = tuple(module_path.parts)

    if parts[-1] == "__init__":  
        parts = parts[:-1]
        doc_path = doc_path.with_name("index.md")
        full_doc_path = full_doc_path.with_name("index.md")

    elif parts[-1] == "__main__":
        continue

    nav[parts] = doc_path.as_posix()

    A = False
    B = False

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:  
        identifier = ".".join(parts)  
        print("::: " + identifier, file=fd)  

        if parts == ('cassini', 'core'):
            print('    inherited_members: true', file=fd)
        
        if parts == ('cassini', 'environment'):
            print("    options:", file=fd)
            print("        filters: []", file=fd)
            print("        members:", file=fd)
            print("            - env", file=fd)
            print("            - _Env", file=fd)


with mkdocs_gen_files.open("api/modules.md", "w") as nav_file:  
    nav_file.writelines(nav.build_literate_nav())
