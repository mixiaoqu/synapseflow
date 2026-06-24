"""Generate graph-friendly JSONL facts from the current source tree."""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "docs" / "generated"
OUTPUT_FILE_PREFIXES = {
    "symbol_fact": "code-graph-symbol-facts",
    "module_relation_fact": "code-graph-module-relations",
    "symbol_relation_fact": "code-graph-symbol-relations",
    "call_fact_endpoint_service": "code-graph-call-facts-endpoints",
    "call_fact_service_dependency": "code-graph-call-facts-services",
    "call_fact_frontend_api": "code-graph-call-facts-frontend",
}
MAX_FACTS_PER_FILE = 500
SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".vue"}
FRONTEND_ALIAS_PREFIX = "@/"
FASTAPI_METHOD_NAMES = {"get", "post", "put", "delete", "patch", "options", "head"}
FRONTEND_PAGE_SUFFIX = "Page.vue"
_JS_FUNCTION_RANGES_CACHE: dict[str, dict[str, tuple[int, int]]] = {}
_PYTHON_FUNCTION_RANGES_CACHE: dict[str, dict[str, tuple[int | None, int | None]]] = {}


@dataclass(frozen=True)
class EntityRef:
    entity_type: str
    name: str
    canonical_name: str
    path: str | None = None
    symbol_kind: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    parent_canonical_name: str | None = None
    aliases: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "entity_type": self.entity_type,
            "name": self.name,
            "canonical_name": self.canonical_name,
        }
        if self.path:
            payload["path"] = self.path
        if self.symbol_kind:
            payload["symbol_kind"] = self.symbol_kind
        if self.start_line is not None:
            payload["start_line"] = self.start_line
        if self.end_line is not None:
            payload["end_line"] = self.end_line
        payload["parent_canonical_name"] = self.parent_canonical_name
        payload["aliases"] = list(self.aliases)
        return payload


class FactWriter:
    def __init__(self) -> None:
        self._seen: set[str] = set()
        self.facts_by_kind: dict[str, list[dict[str, Any]]] = {
            kind: [] for kind in OUTPUT_FILE_PREFIXES
        }
        self.counts: Counter[str] = Counter()

    def add(
        self,
        *,
        kind: str,
        source: EntityRef,
        target: EntityRef,
        relation_type: str,
        text: str,
        relation_attributes: dict[str, Any] | None = None,
    ) -> None:
        relation = {"type": relation_type}
        if relation_attributes:
            relation.update(relation_attributes)
        fact = {
            "kind": kind,
            "source": source.to_payload(),
            "target": target.to_payload(),
            "relation": relation,
            "text": text,
        }
        key = json.dumps(fact, ensure_ascii=False, sort_keys=True)
        if key in self._seen:
            return
        self._seen.add(key)
        self.facts_by_kind.setdefault(kind, []).append(fact)
        self.counts[kind] += 1


def repo_relpath(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def collect_source_files() -> list[Path]:
    files: list[Path] = []
    for root in ("backend/app", "frontend/src", "mcp_server/src"):
        base = REPO_ROOT / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in SOURCE_EXTENSIONS:
                files.append(path)
    return sorted(files)


def module_entity_type(path: Path) -> str:
    rel = repo_relpath(path)
    if "/pages/" in rel:
        return "PAGE"
    if "/config" in rel or rel.endswith((".yaml", ".yml")):
        return "CONFIG"
    return "MODULE"


def build_module_entity(path: Path) -> EntityRef:
    rel = repo_relpath(path)
    return EntityRef(
        entity_type=module_entity_type(path),
        name=path.name,
        canonical_name=rel,
        path=rel,
    )


def classify_symbol_entity_type(path: Path, symbol_kind: str, name: str) -> str:
    rel = repo_relpath(path)
    if symbol_kind in {"class", "component"}:
        if "/pages/" in rel or name.endswith("Page"):
            return "PAGE"
        return "COMPONENT"
    if symbol_kind == "router":
        return "WORKFLOW"
    if symbol_kind == "config_entry":
        return "CONFIG"
    return "OPERATION"


def build_symbol_entity(
    path: Path,
    *,
    name: str,
    symbol_kind: str,
    start_line: int | None,
    end_line: int | None,
    parent_canonical_name: str | None = None,
    aliases: tuple[str, ...] = (),
) -> EntityRef:
    module_canonical_name = repo_relpath(path)
    if parent_canonical_name:
        canonical_name = f"{parent_canonical_name}::{name}"
    else:
        canonical_name = f"{module_canonical_name}::{name}"
    return EntityRef(
        entity_type=classify_symbol_entity_type(path, symbol_kind, name),
        name=name,
        canonical_name=canonical_name,
        symbol_kind=symbol_kind,
        start_line=start_line,
        end_line=end_line,
        parent_canonical_name=parent_canonical_name,
        aliases=aliases,
    )


def describe_symbol_kind(symbol_kind: str) -> str:
    labels = {
        "function": "函数",
        "method": "方法",
        "class": "类",
        "router": "路由容器",
        "component": "组件",
        "config_entry": "配置项",
        "route_handler": "路由处理函数",
    }
    return labels.get(symbol_kind, symbol_kind)


def build_python_module_name(path: Path) -> str | None:
    rel = path.relative_to(REPO_ROOT).as_posix()
    if rel.startswith("backend/app/"):
        suffix = rel[len("backend/") :]
    else:
        return None
    if suffix.endswith("/__init__.py"):
        suffix = suffix[: -len("/__init__.py")]
    elif suffix.endswith(".py"):
        suffix = suffix[:-3]
    return suffix.replace("/", ".")


def module_name_to_symbol_prefix(module_name: str) -> str | None:
    target_path = resolve_python_module_to_file(module_name)
    if target_path is None:
        return None
    return repo_relpath(target_path)


def resolve_python_module_to_file(module_name: str) -> Path | None:
    if not module_name:
        return None
    if not module_name.startswith("app."):
        return None
    relative = Path("backend") / Path(module_name.replace(".", "/"))
    file_path = REPO_ROOT / relative.with_suffix(".py")
    if file_path.exists():
        return file_path
    init_path = REPO_ROOT / relative / "__init__.py"
    if init_path.exists():
        return init_path
    return None


def is_backend_dependency_target(path: Path) -> bool:
    rel = repo_relpath(path)
    return rel.startswith(
        (
            "backend/app/application/",
            "backend/app/services/",
            "backend/app/repositories/",
            "backend/app/agents/",
        )
    )


def extract_python_call_target(expr: ast.AST) -> tuple[str | None, str | None]:
    if isinstance(expr, ast.Attribute):
        if isinstance(expr.value, ast.Name):
            return (expr.value.id, expr.attr)
        if isinstance(expr.value, ast.Call) and isinstance(expr.value.func, ast.Name):
            return (expr.value.func.id, expr.attr)
    return (None, None)


def collect_class_method_ranges(node: ast.ClassDef) -> dict[str, tuple[int | None, int | None]]:
    ranges: dict[str, tuple[int | None, int | None]] = {}
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ranges[child.name] = (getattr(child, "lineno", None), getattr(child, "end_lineno", None))
    return ranges


def collect_python_module_level_ranges(tree: ast.AST) -> dict[str, tuple[int | None, int | None]]:
    ranges: dict[str, tuple[int | None, int | None]] = {}
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ranges[node.name] = (getattr(node, "lineno", None), getattr(node, "end_lineno", None))
    return ranges


def get_python_function_ranges_for_path(path: Path) -> dict[str, tuple[int | None, int | None]]:
    cache_key = repo_relpath(path)
    cached = _PYTHON_FUNCTION_RANGES_CACHE.get(cache_key)
    if cached is not None:
        return cached
    tree = ast.parse(read_text(path), filename=cache_key)
    ranges = collect_python_module_level_ranges(tree)
    _PYTHON_FUNCTION_RANGES_CACHE[cache_key] = ranges
    return ranges


def class_name_to_entity_type(name: str) -> str:
    if name.endswith("Repository"):
        return "MODULE"
    if name.endswith("Service"):
        return "OPERATION"
    return "COMPONENT"


def build_class_method_entity(
    path: Path,
    *,
    class_name: str,
    method_name: str,
    start_line: int | None,
    end_line: int | None,
) -> EntityRef:
    class_entity = build_symbol_entity(
        path,
        name=class_name,
        symbol_kind="class",
        start_line=None,
        end_line=None,
    )
    return EntityRef(
        entity_type="OPERATION",
        name=method_name,
        canonical_name=f"{class_entity.canonical_name}::{method_name}",
        symbol_kind="method",
        start_line=start_line,
        end_line=end_line,
        parent_canonical_name=class_entity.canonical_name,
        aliases=(),
    )


def resolve_python_from_import(path: Path, node: ast.ImportFrom, alias_name: str) -> Path | None:
    module_name = node.module or ""
    current_module = build_python_module_name(path)
    if current_module is None:
        return None

    if node.level:
        current_parts = current_module.split(".")
        package_parts = current_parts[:-1]
        base_parts = package_parts[: max(0, len(package_parts) - node.level + 1)]
        if module_name:
            base_parts.extend(module_name.split("."))
        absolute_module_name = ".".join(part for part in base_parts if part)
    else:
        absolute_module_name = module_name

    candidate_module = ".".join(part for part in [absolute_module_name, alias_name] if part)
    direct = resolve_python_module_to_file(candidate_module)
    if direct is not None:
        return direct
    return resolve_python_module_to_file(absolute_module_name)


def extract_fastapi_route_metadata(node: ast.AST) -> tuple[str | None, str | None]:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return (None, None)
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        if not isinstance(decorator.func, ast.Attribute):
            continue
        method_name = decorator.func.attr
        if method_name not in FASTAPI_METHOD_NAMES:
            continue
        route_path = None
        if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(
            decorator.args[0].value, str
        ):
            route_path = decorator.args[0].value
        return (method_name.upper(), route_path)
    return (None, None)


def add_python_symbol_facts(path: Path, tree: ast.AST, writer: FactWriter) -> None:
    module = build_module_entity(path)

    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef):
            class_entity = build_symbol_entity(
                path,
                name=node.name,
                symbol_kind="class",
                start_line=getattr(node, "lineno", None),
                end_line=getattr(node, "end_lineno", None),
            )
            writer.add(
                kind="symbol_fact",
                source=module,
                target=class_entity,
                relation_type="DECLARES",
                text=f"文件 {module.canonical_name} 声明了类 {node.name}。",
            )
            for child in node.body:
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                method_name = child.name
                method_kind = "method"
                method_entity = build_symbol_entity(
                    path,
                    name=method_name,
                    symbol_kind=method_kind,
                    start_line=getattr(child, "lineno", None),
                    end_line=getattr(child, "end_lineno", None),
                    parent_canonical_name=class_entity.canonical_name,
                )
                writer.add(
                    kind="symbol_fact",
                    source=module,
                    target=method_entity,
                    relation_type="DECLARES",
                    text=f"文件 {module.canonical_name} 中，类 {node.name} 声明了方法 {method_name}。",
                )
            continue

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            http_method, route_path = extract_fastapi_route_metadata(node)
            symbol_kind = "route_handler" if http_method else "function"
            function_entity = build_symbol_entity(
                path,
                name=node.name,
                symbol_kind=symbol_kind,
                start_line=getattr(node, "lineno", None),
                end_line=getattr(node, "end_lineno", None),
            )
            if http_method and route_path is not None:
                normalized_route_path = route_path or "/"
                text = (
                    f"文件 {module.canonical_name} 声明了 {http_method} {normalized_route_path} "
                    f"路由处理函数 {node.name}。"
                )
            else:
                text = f"文件 {module.canonical_name} 声明了函数 {node.name}。"
            writer.add(
                kind="symbol_fact",
                source=module,
                target=function_entity,
                relation_type="DECLARES",
                text=text,
            )
            continue

        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        call_name = ""
        if isinstance(node.value.func, ast.Name):
            call_name = node.value.func.id
        elif isinstance(node.value.func, ast.Attribute):
            call_name = node.value.func.attr
        if call_name != "APIRouter":
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            router_entity = build_symbol_entity(
                path,
                name=target.id,
                symbol_kind="router",
                start_line=getattr(node, "lineno", None),
                end_line=getattr(node, "end_lineno", None),
            )
            writer.add(
                kind="symbol_fact",
                source=module,
                target=router_entity,
                relation_type="DECLARES",
                text=f"文件 {module.canonical_name} 声明了路由容器 {target.id}。",
            )


def add_python_import_facts(path: Path, tree: ast.AST, writer: FactWriter) -> dict[str, Path]:
    module = build_module_entity(path)
    import_aliases: dict[str, Path] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target_path = resolve_python_module_to_file(alias.name)
                if target_path is None:
                    continue
                local_name = alias.asname or alias.name.split(".")[-1]
                import_aliases[local_name] = target_path
                writer.add(
                    kind="module_relation_fact",
                    source=module,
                    target=build_module_entity(target_path),
                    relation_type="IMPORTS",
                    text=f"文件 {module.canonical_name} 导入了模块 {repo_relpath(target_path)}。",
                )
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                target_path = resolve_python_from_import(path, node, alias.name)
                if target_path is None:
                    continue
                local_name = alias.asname or alias.name
                import_aliases[local_name] = target_path
                writer.add(
                    kind="module_relation_fact",
                    source=module,
                    target=build_module_entity(target_path),
                    relation_type="IMPORTS",
                    text=f"文件 {module.canonical_name} 导入了模块 {repo_relpath(target_path)}。",
                )
    return import_aliases


def expression_to_name(expr: ast.AST) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        base = expression_to_name(expr.value)
        if base:
            return f"{base}.{expr.attr}"
    return None


def add_python_router_facts(
    path: Path,
    tree: ast.AST,
    import_aliases: dict[str, Path],
    writer: FactWriter,
) -> None:
    module = build_module_entity(path)
    local_router_names: set[str] = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call_name = ""
            if isinstance(node.value.func, ast.Name):
                call_name = node.value.func.id
            elif isinstance(node.value.func, ast.Attribute):
                call_name = node.value.func.attr
            if call_name != "APIRouter":
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    local_router_names.add(target.id)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "include_router":
            continue
        source_name = expression_to_name(node.func.value)
        if not source_name or source_name not in local_router_names:
            continue
        if not node.args:
            continue
        target_name = expression_to_name(node.args[0])
        if not target_name:
            continue

        alias_root, _, alias_tail = target_name.partition(".")
        target_path = import_aliases.get(alias_root)
        if target_path is None:
            continue
        target_symbol_name = alias_tail or "router"
        target_symbol = build_symbol_entity(
            target_path,
            name=target_symbol_name,
            symbol_kind="router",
            start_line=None,
            end_line=None,
        )
        source_symbol = build_symbol_entity(
            path,
            name=source_name,
            symbol_kind="router",
            start_line=None,
            end_line=None,
        )
        prefix = None
        for keyword in node.keywords:
            if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant):
                if isinstance(keyword.value.value, str):
                    prefix = keyword.value.value
        relation_attributes = {"prefix": prefix} if prefix else None
        if prefix:
            text = (
                f"文件 {module.canonical_name} 中的路由容器 {source_name} "
                f"挂载了 {target_symbol.canonical_name}，前缀为 {prefix}。"
            )
        else:
            text = (
                f"文件 {module.canonical_name} 中的路由容器 {source_name} "
                f"挂载了 {target_symbol.canonical_name}。"
            )
        writer.add(
            kind="symbol_relation_fact",
            source=source_symbol,
            target=target_symbol,
            relation_type="ROUTES_TO",
            text=text,
            relation_attributes=relation_attributes,
        )


def add_python_endpoint_service_calls(path: Path, tree: ast.AST, writer: FactWriter) -> None:
    if "/api/v1/endpoints/" not in repo_relpath(path):
        return

    imported_classes: dict[str, tuple[Path, str]] = {}
    imported_functions: dict[str, Path] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        for alias in node.names:
            target_path = resolve_python_from_import(path, node, alias.name)
            if target_path is None:
                continue
            local_name = alias.asname or alias.name
            if alias.name.endswith("Service"):
                imported_classes[local_name] = (target_path, alias.name)
            else:
                imported_functions[local_name] = target_path

    module_level_ranges = collect_python_module_level_ranges(tree)
    for node in getattr(tree, "body", []):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        http_method, route_path = extract_fastapi_route_metadata(node)
        if http_method is None:
            continue
        source_entity = build_symbol_entity(
            path,
            name=node.name,
            symbol_kind="route_handler",
            start_line=getattr(node, "lineno", None),
            end_line=getattr(node, "end_lineno", None),
        )

        local_services: dict[str, tuple[Path, str]] = {}
        for subnode in ast.walk(node):
            if not isinstance(subnode, ast.Assign):
                continue
            if not isinstance(subnode.value, ast.Call):
                continue
            if not isinstance(subnode.value.func, ast.Name):
                continue
            service_binding = imported_classes.get(subnode.value.func.id)
            if service_binding is None:
                continue
            for target in subnode.targets:
                if isinstance(target, ast.Name):
                    local_services[target.id] = service_binding

        seen_targets: set[str] = set()
        for subnode in ast.walk(node):
            if not isinstance(subnode, ast.Call):
                continue
            service_var, method_name = extract_python_call_target(subnode.func)
            if service_var and service_var in local_services and method_name:
                target_path, class_name = local_services[service_var]
                target_entity = build_class_method_entity(
                    target_path,
                    class_name=class_name,
                    method_name=method_name,
                    start_line=None,
                    end_line=None,
                )
                target_key = target_entity.canonical_name
                if target_key in seen_targets:
                    continue
                seen_targets.add(target_key)
                writer.add(
                    kind="call_fact_endpoint_service",
                    source=source_entity,
                    target=target_entity,
                    relation_type="CALLS",
                    text=(
                        f"接口处理函数 {source_entity.name} 调用了 "
                        f"{class_name}.{method_name}。"
                    ),
                )
                continue

            if isinstance(subnode.func, ast.Name):
                function_name = subnode.func.id
                target_path = imported_functions.get(function_name)
                if target_path is None:
                    continue
                if function_name.startswith("get_") and function_name.endswith("_service"):
                    target_entity = build_symbol_entity(
                        target_path,
                        name=function_name,
                        symbol_kind="function",
                        start_line=module_level_ranges.get(function_name, (None, None))[0],
                        end_line=module_level_ranges.get(function_name, (None, None))[1],
                    )
                    target_key = target_entity.canonical_name
                    if target_key in seen_targets:
                        continue
                    seen_targets.add(target_key)
                    writer.add(
                        kind="call_fact_endpoint_service",
                        source=source_entity,
                        target=target_entity,
                        relation_type="CALLS",
                        text=f"接口处理函数 {source_entity.name} 调用了 {function_name}。",
                    )


def add_python_service_dependency_calls(path: Path, tree: ast.AST, writer: FactWriter) -> None:
    rel = repo_relpath(path)
    if not ("/application/" in rel or "/services/" in rel):
        return

    imported_classes: dict[str, tuple[Path, str]] = {}
    imported_functions: dict[str, Path] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        for alias in node.names:
            target_path = resolve_python_from_import(path, node, alias.name)
            if target_path is None:
                continue
            local_name = alias.asname or alias.name
            if alias.name.endswith(("Repository", "Service")):
                imported_classes[local_name] = (target_path, alias.name)
            else:
                imported_functions[local_name] = target_path

    module_level_ranges = collect_python_module_level_ranges(tree)
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.ClassDef):
            continue
        method_ranges = collect_class_method_ranges(node)
        class_name = node.name
        if not class_name.endswith("Service"):
            continue

        local_dependency_attrs: dict[str, tuple[Path, str]] = {}
        for child in node.body:
            if not isinstance(child, ast.FunctionDef) or child.name != "__init__":
                continue
            for subnode in ast.walk(child):
                if not isinstance(subnode, ast.Assign):
                    continue
                if len(subnode.targets) != 1:
                    continue
                target = subnode.targets[0]
                if not isinstance(target, ast.Attribute):
                    continue
                if not isinstance(target.value, ast.Name) or target.value.id != "self":
                    continue
                if not isinstance(subnode.value, ast.Call):
                    continue
                if not isinstance(subnode.value.func, ast.Name):
                    continue
                binding = imported_classes.get(subnode.value.func.id)
                if binding is not None:
                    local_dependency_attrs[target.attr] = binding

        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if child.name == "__init__":
                continue
            source_entity = build_class_method_entity(
                path,
                class_name=class_name,
                method_name=child.name,
                start_line=method_ranges.get(child.name, (None, None))[0],
                end_line=method_ranges.get(child.name, (None, None))[1],
            )
            seen_targets: set[str] = set()
            for subnode in ast.walk(child):
                if not isinstance(subnode, ast.Call):
                    continue

                dependency_attr = None
                method_name = None
                if isinstance(subnode.func, ast.Attribute):
                    method_name = subnode.func.attr
                    if isinstance(subnode.func.value, ast.Attribute):
                        if (
                            isinstance(subnode.func.value.value, ast.Name)
                            and subnode.func.value.value.id == "self"
                        ):
                            dependency_attr = subnode.func.value.attr
                if dependency_attr and method_name and dependency_attr in local_dependency_attrs:
                    target_path, dependency_class = local_dependency_attrs[dependency_attr]
                    if not is_backend_dependency_target(target_path):
                        continue
                    target_entity = build_class_method_entity(
                        target_path,
                        class_name=dependency_class,
                        method_name=method_name,
                        start_line=None,
                        end_line=None,
                    )
                    target_key = target_entity.canonical_name
                    if target_key in seen_targets:
                        continue
                    seen_targets.add(target_key)
                    writer.add(
                        kind="call_fact_service_dependency",
                        source=source_entity,
                        target=target_entity,
                        relation_type="CALLS",
                        text=(
                            f"应用服务 {class_name}.{child.name} 调用了 "
                            f"{dependency_class}.{method_name}。"
                        ),
                    )
                    continue

                if isinstance(subnode.func, ast.Name):
                    function_name = subnode.func.id
                    target_path = imported_functions.get(function_name)
                    if target_path is None:
                        continue
                    if not is_backend_dependency_target(target_path):
                        continue
                    target_entity = build_symbol_entity(
                        target_path,
                        name=function_name,
                        symbol_kind="function",
                        start_line=get_python_function_ranges_for_path(target_path).get(
                            function_name, (None, None)
                        )[0],
                        end_line=get_python_function_ranges_for_path(target_path).get(
                            function_name, (None, None)
                        )[1],
                    )
                    target_key = target_entity.canonical_name
                    if target_key in seen_targets:
                        continue
                    seen_targets.add(target_key)
                    writer.add(
                        kind="call_fact_service_dependency",
                        source=source_entity,
                        target=target_entity,
                        relation_type="CALLS",
                        text=f"应用服务 {class_name}.{child.name} 调用了 {function_name}。",
                    )


def script_segments_for_vue(content: str) -> str:
    matches = re.findall(r"<script[^>]*>(.*?)</script>", content, flags=re.DOTALL | re.IGNORECASE)
    if not matches:
        return content
    return "\n".join(matches)


def resolve_js_import(path: Path, specifier: str) -> Path | None:
    if specifier.startswith(FRONTEND_ALIAS_PREFIX):
        candidate = REPO_ROOT / "frontend" / "src" / specifier[len(FRONTEND_ALIAS_PREFIX) :]
    elif specifier.startswith("."):
        candidate = (path.parent / specifier).resolve()
    else:
        return None

    if candidate.is_file() and candidate.suffix in SOURCE_EXTENSIONS:
        return candidate

    candidates = [candidate]
    if candidate.suffix:
        candidates = [candidate]
    else:
        candidates = [
            candidate.with_suffix(".ts"),
            candidate.with_suffix(".tsx"),
            candidate.with_suffix(".js"),
            candidate.with_suffix(".jsx"),
            candidate.with_suffix(".vue"),
            candidate / "index.ts",
            candidate / "index.tsx",
            candidate / "index.js",
            candidate / "index.jsx",
            candidate / "index.vue",
        ]
    for file_path in candidates:
        if file_path.exists() and file_path.is_file():
            return file_path
    return None


def line_number_at(content: str, index: int) -> int:
    return content.count("\n", 0, index) + 1


def add_js_import_facts(path: Path, script_content: str, writer: FactWriter) -> dict[str, Path]:
    module = build_module_entity(path)
    import_aliases: dict[str, Path] = {}
    pattern = re.compile(r"import\s+(.*?)\s+from\s+[\"']([^\"']+)[\"']", re.DOTALL)

    for match in pattern.finditer(script_content):
        specifier = match.group(2).strip()
        target_path = resolve_js_import(path, specifier)
        if target_path is None:
            continue
        clause = match.group(1).strip()
        names: list[str] = []
        if clause.startswith("{"):
            names.extend(
                part.strip().split(" as ")[-1].strip()
                for part in clause.strip("{} ").split(",")
                if part.strip()
            )
        else:
            default_name = clause.split(",")[0].strip()
            if default_name and default_name != "*":
                names.append(default_name)
            star_match = re.search(r"\*\s+as\s+([A-Za-z_$][\w$]*)", clause)
            if star_match:
                names.append(star_match.group(1))
            named_match = re.search(r"\{(.*?)\}", clause, flags=re.DOTALL)
            if named_match:
                names.extend(
                    part.strip().split(" as ")[-1].strip()
                    for part in named_match.group(1).split(",")
                    if part.strip()
                )
        for name in names:
            import_aliases[name] = target_path
        writer.add(
            kind="module_relation_fact",
            source=module,
            target=build_module_entity(target_path),
            relation_type="IMPORTS",
            text=f"文件 {module.canonical_name} 导入了模块 {repo_relpath(target_path)}。",
        )
    return import_aliases


def add_js_symbol_facts(path: Path, script_content: str, writer: FactWriter) -> None:
    module = build_module_entity(path)
    patterns = [
        (re.compile(r"(?m)^\s*export\s+async\s+function\s+([A-Za-z_$][\w$]*)\s*\("), "function"),
        (re.compile(r"(?m)^\s*export\s+function\s+([A-Za-z_$][\w$]*)\s*\("), "function"),
        (re.compile(r"(?m)^\s*async\s+function\s+([A-Za-z_$][\w$]*)\s*\("), "function"),
        (re.compile(r"(?m)^\s*function\s+([A-Za-z_$][\w$]*)\s*\("), "function"),
        (re.compile(r"(?m)^\s*export\s+class\s+([A-Za-z_$][\w$]*)\b"), "class"),
        (re.compile(r"(?m)^\s*class\s+([A-Za-z_$][\w$]*)\b"), "class"),
        (
            re.compile(r"(?m)^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("),
            "function",
        ),
        (
            re.compile(r"(?m)^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*createRouter\s*\("),
            "router",
        ),
        (
            re.compile(r"(?m)^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*defineStore\s*\("),
            "config_entry",
        ),
    ]

    seen_symbols: set[str] = set()
    for pattern, symbol_kind in patterns:
        for match in pattern.finditer(script_content):
            name = match.group(1)
            if name in seen_symbols:
                continue
            seen_symbols.add(name)
            start_line = line_number_at(script_content, match.start(1))
            target = build_symbol_entity(
                path,
                name=name,
                symbol_kind=symbol_kind,
                start_line=start_line,
                end_line=start_line,
            )
            writer.add(
                kind="symbol_fact",
                source=module,
                target=target,
                relation_type="DECLARES",
                text=f"文件 {module.canonical_name} 声明了{describe_symbol_kind(symbol_kind)} {name}。",
            )


def split_route_objects(route_block: str) -> list[str]:
    objects: list[str] = []
    depth = 0
    start = -1
    for index, char in enumerate(route_block):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start != -1:
                objects.append(route_block[start : index + 1])
                start = -1
    return objects


def join_route_path(parent_path: str, child_path: str) -> str:
    parent = (parent_path or "").strip()
    child = (child_path or "").strip()
    if not parent:
        return child or "/"
    if not child:
        return parent or "/"
    if child.startswith("/"):
        return child
    if parent.endswith("/"):
        return f"{parent}{child}"
    return f"{parent}/{child}"


def extract_child_routes_block(route_object: str) -> str | None:
    marker = re.search(r"children\s*:\s*\[", route_object)
    if marker is None:
        return None
    start = marker.end()
    depth = 1
    for index in range(start, len(route_object)):
        char = route_object[index]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return route_object[start:index]
    return None


def iter_frontend_route_entries(route_block: str, parent_path: str = "") -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for route_object in split_route_objects(route_block):
        path_match = re.search(r'path\s*:\s*"([^"]*)"', route_object)
        component_match = re.search(r"component\s*:\s*([A-Za-z_$][\w$]*)", route_object)
        own_path = path_match.group(1).strip() if path_match else ""
        full_path = join_route_path(parent_path, own_path)
        if component_match:
            entries.append((full_path, component_match.group(1).strip()))
        child_block = extract_child_routes_block(route_object)
        if child_block:
            entries.extend(iter_frontend_route_entries(child_block, full_path))
    return entries


def add_frontend_route_facts(
    path: Path,
    script_content: str,
    import_aliases: dict[str, Path],
    writer: FactWriter,
) -> None:
    if repo_relpath(path) != "frontend/src/router/index.ts":
        return
    module = build_module_entity(path)
    routes_match = re.search(r"routes\s*:\s*\[(.*)\]\s*,\s*}\s*\)\s*;", script_content, re.DOTALL)
    if not routes_match:
        return
    for route_path, component_name in iter_frontend_route_entries(routes_match.group(1)):
        component_path = import_aliases.get(component_name)
        if component_path is None:
            continue
        text = f"前端路由 {route_path} 渲染页面模块 {repo_relpath(component_path)}。"
        writer.add(
            kind="module_relation_fact",
            source=module,
            target=build_module_entity(component_path),
            relation_type="ROUTES_TO",
            text=text,
            relation_attributes={"route_path": route_path},
        )


def extract_frontend_component_name(path: Path, raw_content: str) -> str:
    define_options_match = re.search(r'name\s*:\s*"([^"]+)"', raw_content)
    if define_options_match:
        return define_options_match.group(1).strip()
    if path.name.endswith(FRONTEND_PAGE_SUFFIX):
        return path.name[: -len(".vue")]
    return path.stem


def collect_js_function_ranges(script_content: str) -> dict[str, tuple[int, int]]:
    ranges: dict[str, tuple[int, int]] = {}
    patterns = [
        re.compile(r"(?m)^\s*export\s+async\s+function\s+([A-Za-z_$][\w$]*)\s*\("),
        re.compile(r"(?m)^\s*export\s+function\s+([A-Za-z_$][\w$]*)\s*\("),
        re.compile(r"(?m)^\s*async\s+function\s+([A-Za-z_$][\w$]*)\s*\("),
        re.compile(r"(?m)^\s*function\s+([A-Za-z_$][\w$]*)\s*\("),
        re.compile(r"(?m)^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("),
    ]
    for pattern in patterns:
        for match in pattern.finditer(script_content):
            name = match.group(1)
            line = line_number_at(script_content, match.start(1))
            ranges.setdefault(name, (line, line))
    return ranges


def get_js_function_ranges_for_path(path: Path) -> dict[str, tuple[int, int]]:
    cache_key = repo_relpath(path)
    cached = _JS_FUNCTION_RANGES_CACHE.get(cache_key)
    if cached is not None:
        return cached
    raw_content = read_text(path)
    script_content = script_segments_for_vue(raw_content) if path.suffix == ".vue" else raw_content
    ranges = collect_js_function_ranges(script_content)
    _JS_FUNCTION_RANGES_CACHE[cache_key] = ranges
    return ranges


def add_frontend_api_calls(
    path: Path,
    raw_content: str,
    script_content: str,
    import_aliases: dict[str, Path],
    writer: FactWriter,
) -> None:
    rel = repo_relpath(path)
    if "/pages/" not in rel and "/composables/" not in rel:
        return

    source_symbol_kind = "component" if rel.endswith(".vue") else "function"
    source_name = extract_frontend_component_name(path, raw_content)
    source_entity = build_symbol_entity(
        path,
        name=source_name,
        symbol_kind=source_symbol_kind,
        start_line=1,
        end_line=max(1, script_content.count("\n") + 1),
    )

    js_ranges = collect_js_function_ranges(script_content)
    seen_targets: set[str] = set()
    for local_name, target_path in import_aliases.items():
        target_rel = repo_relpath(target_path)
        if not target_rel.startswith("frontend/src/shared/api/"):
            continue
        call_pattern = re.compile(rf"(?<![\w$]){re.escape(local_name)}\s*\(")
        if call_pattern.search(script_content) is None:
            continue
        target_entity = build_symbol_entity(
            target_path,
            name=local_name,
            symbol_kind="function",
            start_line=get_js_function_ranges_for_path(target_path).get(local_name, (None, None))[0],
            end_line=get_js_function_ranges_for_path(target_path).get(local_name, (None, None))[1],
        )
        target_key = target_entity.canonical_name
        if target_key in seen_targets:
            continue
        seen_targets.add(target_key)
        label = "页面" if "/pages/" in rel else "组合式函数"
        writer.add(
            kind="call_fact_frontend_api",
            source=source_entity,
            target=target_entity,
            relation_type="CALLS",
            text=f"{label} {source_name} 调用了前端 API 方法 {local_name}。",
        )


def process_python_file(path: Path, writer: FactWriter) -> None:
    content = read_text(path)
    tree = ast.parse(content, filename=repo_relpath(path))
    add_python_symbol_facts(path, tree, writer)
    import_aliases = add_python_import_facts(path, tree, writer)
    add_python_router_facts(path, tree, import_aliases, writer)
    add_python_endpoint_service_calls(path, tree, writer)
    add_python_service_dependency_calls(path, tree, writer)


def process_js_like_file(path: Path, writer: FactWriter) -> None:
    raw_content = read_text(path)
    script_content = script_segments_for_vue(raw_content) if path.suffix == ".vue" else raw_content
    add_js_symbol_facts(path, script_content, writer)
    import_aliases = add_js_import_facts(path, script_content, writer)
    add_frontend_route_facts(path, script_content, import_aliases, writer)
    add_frontend_api_calls(path, raw_content, script_content, import_aliases, writer)


def batched(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def build_output_path(kind: str, batch_index: int) -> Path:
    prefix = OUTPUT_FILE_PREFIXES[kind]
    return OUTPUT_DIR / f"{prefix}-{batch_index:03d}.jsonl"


def cleanup_previous_outputs() -> None:
    for prefix in OUTPUT_FILE_PREFIXES.values():
        for path in OUTPUT_DIR.glob(f"{prefix}-*.jsonl"):
            path.unlink()


def generate() -> tuple[dict[str, list[Path]], Counter[str]]:
    writer = FactWriter()
    for path in collect_source_files():
        if path.suffix == ".py":
            process_python_file(path, writer)
        else:
            process_js_like_file(path, writer)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_previous_outputs()
    output_paths: dict[str, list[Path]] = {}
    for kind, facts in writer.facts_by_kind.items():
        kind_paths: list[Path] = []
        for batch_index, batch in enumerate(batched(facts, MAX_FACTS_PER_FILE), start=1):
            output_path = build_output_path(kind, batch_index)
            kind_paths.append(output_path)
            with output_path.open("w", encoding="utf-8", newline="\n") as handle:
                for fact in batch:
                    handle.write(json.dumps(fact, ensure_ascii=False) + "\n")
        output_paths[kind] = kind_paths
    return output_paths, writer.counts


def main() -> None:
    output_paths, counts = generate()
    summary = {
        "output_paths": {
            kind: [repo_relpath(path) for path in paths]
            for kind, paths in output_paths.items()
        },
        "fact_count": sum(counts.values()),
        "kinds": dict(counts),
        "max_facts_per_file": MAX_FACTS_PER_FILE,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
