#! python3  # noqa: E265

"""
Keep the vendored APSG free of a hard scipy dependency.

Moves every module-level ``import scipy...`` / ``from scipy... import ...`` in
``websdb/apsg`` into the functions that use the imported names, so ``import apsg``
and the code paths the plugin uses work without scipy. Run it after every re-sync
of ``websdb/apsg`` from upstream.

Usage from the repo root folder:

.. code-block:: bash

    # rewrite websdb/apsg in place
    python scripts/apsg_lazy_scipy.py
    # only report remaining module-level scipy imports (exit 1 if any)
    python scripts/apsg_lazy_scipy.py --check
"""

# standard library
import ast
import sys
from pathlib import Path

APSG_DIR = Path(__file__).resolve().parent.parent / "websdb" / "apsg"


def _is_scipy(node):
    if isinstance(node, ast.ImportFrom):
        return bool(node.module) and node.module.split(".")[0] == "scipy"
    if isinstance(node, ast.Import):
        return any(a.name.split(".")[0] == "scipy" for a in node.names)
    return False


def _import_statements(node):
    """local name -> single-name import statement, for one import node."""
    stmts = {}
    for alias in node.names:
        local = alias.asname or alias.name.split(".")[0]
        if isinstance(node, ast.ImportFrom):
            stmt = "from {} import {}".format(node.module, alias.name)
        else:
            stmt = "import {}".format(alias.name)
        if alias.asname:
            stmt += " as {}".format(alias.asname)
        stmts[local] = stmt
    return stmts


def _stored_names(func):
    return {
        n.id
        for n in ast.walk(func)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
    }


def make_lazy(path):
    """Rewrite one module. Returns the number of import nodes moved."""
    src = path.read_text()
    tree = ast.parse(src)
    scipy_nodes = [n for n in tree.body if _is_scipy(n)]
    if not scipy_nodes:
        return 0
    names = {}
    drop = set()
    for node in scipy_nodes:
        names.update(_import_statements(node))
        drop.update(range(node.lineno - 1, node.end_lineno))

    lines = src.splitlines(keepends=True)
    inserts = {}  # line index -> (indent, set of import statements)
    unresolved = set()

    def visit(node, outer_func):
        for child in ast.iter_child_nodes(node):
            func = outer_func
            if outer_func is None and isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                func = child
            if (
                isinstance(child, ast.Name)
                and isinstance(child.ctx, ast.Load)
                and child.id in names
            ):
                if func is None:
                    unresolved.add(child.id)
                elif child.id not in _stored_names(func):
                    body0 = func.body[0]
                    is_doc = (
                        isinstance(body0, ast.Expr)
                        and isinstance(body0.value, ast.Constant)
                        and isinstance(body0.value.value, str)
                    )
                    at = body0.end_lineno if is_doc else body0.lineno - 1
                    first = lines[body0.lineno - 1]
                    indent = first[: len(first) - len(first.lstrip())]
                    inserts.setdefault(at, (indent, set()))[1].add(names[child.id])
            visit(child, func)

    visit(tree, None)
    if unresolved:
        raise SystemExit(
            "{}: scipy names used outside any function, fix by hand: {}".format(
                path, ", ".join(sorted(unresolved))
            )
        )

    out = []
    for i, line in enumerate(lines):
        if i in inserts:
            indent, stmts = inserts[i]
            out.extend("{}{}\n".format(indent, s) for s in sorted(stmts))
        if i not in drop:
            out.append(line)
    path.write_text("".join(out))
    return len(scipy_nodes)


def main(argv):
    check = "--check" in argv
    found = False
    for path in sorted(APSG_DIR.rglob("*.py")):
        if check:
            tree = ast.parse(path.read_text())
            for node in tree.body:
                if _is_scipy(node):
                    found = True
                    print("{}:{}: module-level scipy import".format(path, node.lineno))
        else:
            moved = make_lazy(path)
            if moved:
                print("{}: moved {} scipy import(s)".format(path, moved))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
