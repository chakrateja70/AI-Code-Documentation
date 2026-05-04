"""
src/services/code_parser.py

Code Parser (AST Analysis) step.
Parses source code files using tree-sitter to extract symbols and imports.
This version uses manual AST traversal to ensure compatibility across all
tree-sitter python bindings (0.21, 0.22, 0.25+).
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

from src.core.models import FileInfo, ParsedFile, SymbolInfo


# ---------------------------------------------------------------------------
# Extension → module_name
# ---------------------------------------------------------------------------
_EXTENSION_MAP: Dict[str, str] = {
    ".py":   "tree_sitter_python",
    ".js":   "tree_sitter_javascript",
    ".jsx":  "tree_sitter_javascript",
    ".ts":   "tree_sitter_typescript",
    ".tsx":  "tree_sitter_typescript",
    ".java": "tree_sitter_java",
    ".go":   "tree_sitter_go",
}

# ---------------------------------------------------------------------------
# Parser cache
# ---------------------------------------------------------------------------
_PARSERS: Dict[str, object] = {}   # module_name → tree_sitter.Parser


def _get_parser(module_name: str) -> Optional[object]:
    """
    Build (and cache) a tree-sitter Parser for *module_name*.
    """
    if module_name in _PARSERS:
        return _PARSERS[module_name]

    try:
        import importlib
        from tree_sitter import Language, Parser

        ts_mod = importlib.import_module(module_name)

        # tree-sitter-python 0.21+ exposes .language()
        if hasattr(ts_mod, "language"):
            lang = Language(ts_mod.language())
        else:
            # Older packages expose the PyCapsule directly
            lang = Language(ts_mod)

        parser = Parser(lang)
        _PARSERS[module_name] = parser
        return parser
    except Exception:
        return None


# ---------------------------------------------------------------------------
# AST Traversal definitions per language
# ---------------------------------------------------------------------------
# We map file extensions to sets of AST node types that indicate functions, classes, and imports.

_AST_KINDS = {
    "tree_sitter_python": {
        "function": {"function_definition"},
        "class": {"class_definition"},
        "import": {"import_statement", "import_from_statement"},
    },
    "tree_sitter_javascript": {
        "function": {"function_declaration", "method_definition", "arrow_function"},
        "class": {"class_declaration"},
        "import": {"import_statement"},
    },
    "tree_sitter_typescript": {
        "function": {"function_declaration", "method_definition", "arrow_function"},
        "class": {"class_declaration"},
        "import": {"import_statement"},
    },
    "tree_sitter_java": {
        "function": {"method_declaration"},
        "class": {"class_declaration"},
        "import": {"import_declaration"},
    },
    "tree_sitter_go": {
        "function": {"function_declaration", "method_declaration"},
        "class": {"type_declaration"}, # Not exactly class, but structures
        "import": {"import_declaration"},
    },
}

def _get_name_for_node(node) -> str:
    """Find the name identifier of a function/class node."""
    # The name is usually the first child of type 'identifier', 'property_identifier', or similar.
    # We check named children to find it.
    for child in node.children:
        if child.type in ("identifier", "property_identifier", "type_identifier", "name"):
            text = child.text
            return text.decode("utf-8", errors="replace") if text else ""
        
        # Sometimes (like in Java or Go), the name is an 'identifier' inside the node
        if child.is_named and child.type.endswith("identifier"):
            text = child.text
            return text.decode("utf-8", errors="replace") if text else ""
    return ""


def _extract_symbols_and_imports(
    content: bytes,
    parser,
    module_name: str,
) -> Tuple[List[SymbolInfo], List[str]]:
    """
    Manually traverse the AST and extract symbols and imports.
    """
    tree = parser.parse(content)
    root = tree.root_node

    symbols: List[SymbolInfo] = []
    imports: List[str] = []

    kinds = _AST_KINDS.get(module_name)
    if not kinds:
        return symbols, imports

    func_types = kinds["function"]
    class_types = kinds["class"]
    import_types = kinds["import"]

    def walk(node, parent_name: Optional[str] = None):
        node_type = node.type
        current_name = parent_name

        if node_type in import_types:
            text = node.text
            if text:
                imports.append(text.decode("utf-8", errors="replace").strip())
        elif node_type in class_types:
            name = _get_name_for_node(node)
            if name:
                symbols.append(SymbolInfo(
                    kind="class",
                    name=name,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    parent=parent_name
                ))
                current_name = name
        elif node_type in func_types:
            name = _get_name_for_node(node)
            if name:
                symbols.append(SymbolInfo(
                    kind="function",
                    name=name,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    parent=parent_name
                ))
                # Usually we don't track functions as parents for other symbols
                # unless we want to track nested functions. We'll leave it as is.

        for child in node.children:
            walk(child, current_name)

    try:
        walk(root)
    except Exception:
        pass

    return symbols, imports


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_file(file_info: FileInfo) -> ParsedFile:
    """
    Parse a single source file and return a ``ParsedFile`` containing symbols
    and imports.

    Returns an empty ``ParsedFile`` (no symbols, no imports) when:
    - the file has no readable content,
    - the extension is not supported, or
    - the required tree-sitter language package is not installed.
    """
    if not file_info.content:
        return ParsedFile(relative_path=file_info.relative_path, symbols=[], imports=[])

    ext = file_info.extension.lower()
    if ext not in _EXTENSION_MAP:
        return ParsedFile(relative_path=file_info.relative_path, symbols=[], imports=[])

    module_name = _EXTENSION_MAP[ext]
    parser = _get_parser(module_name)

    if parser is None:
        # Language package not installed — skip silently.
        return ParsedFile(relative_path=file_info.relative_path, symbols=[], imports=[])

    try:
        content_bytes = file_info.content.encode(file_info.encoding or "utf-8",
                                                  errors="replace")
        symbols, imports = _extract_symbols_and_imports(
            content_bytes, parser, module_name
        )
    except Exception:
        return ParsedFile(relative_path=file_info.relative_path, symbols=[], imports=[])

    return ParsedFile(
        relative_path=file_info.relative_path,
        symbols=symbols,
        imports=imports,
    )