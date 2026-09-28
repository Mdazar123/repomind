"""Focused checks for a Python backend. Every finding cites a line."""

from __future__ import annotations

import ast

from repomind.analysis.detectors import _enclosing_function, _finding, _line

_HTTP = {"get", "post", "put", "patch", "delete", "head", "request", "urlopen"}
_ROUTE = {"get", "post", "put", "patch", "delete", "head", "options", "api_route"}
_BLOCKING = {
    "time.sleep",
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.patch",
    "requests.delete",
    "requests.request",
    "urllib.request.urlopen",
    "subprocess.run",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
}
_QUERY = {"execute", "executemany", "executescript", "query", "find_one"}
_SECRET_NAMES = {"password", "passwd", "secret", "api_key", "apikey", "access_token", "private_key"}


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _has_keyword(node: ast.Call, name: str) -> bool:
    return any(keyword.arg == name for keyword in node.keywords)


def _route_decorator(node: ast.AST) -> ast.Call | None:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    for decorator in node.decorator_list:
        call = decorator if isinstance(decorator, ast.Call) else None
        if call is None:
            continue
        name = _dotted(call.func)
        if name.split(".")[-1] in _ROUTE:
            return call
    return None


def _in_loop(tree: ast.AST, target: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            for child in ast.walk(node):
                if child is target:
                    return True
    return False


def _retry_decorator(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    for decorator in node.decorator_list:
        name = _dotted(decorator.func if isinstance(decorator, ast.Call) else decorator)
        if "retry" in name.lower():
            return True
    return False


def extra_checks(tree: ast.AST, source: str, rel: str) -> list[dict]:
    found: list[dict] = []
    found.extend(_http_calls(tree, source, rel))
    found.extend(_blocking_and_routes(tree, source, rel))
    found.extend(_dependencies(tree, source, rel))
    found.extend(_exceptions(tree, source, rel))
    found.extend(_weak_auth(tree, source, rel))
    found.extend(_sql(tree, source, rel))
    found.extend(_secrets(tree, source, rel))
    found.extend(_shell(tree, source, rel))
    found.extend(_resources(tree, source, rel))
    found.extend(_query_loops(tree, source, rel))
    return found


def _http_calls(tree: ast.AST, source: str, rel: str) -> list[dict]:
    found: list[dict] = []
    retries = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted(node.func)
        short = name.split(".")[-1]
        if short not in _HTTP or not any(prefix in name for prefix in ("requests.", "httpx.", "urllib.")):
            continue
        function = _enclosing_function(tree, node)
        owner = _owner_function(tree, node)
        if not _has_keyword(node, "timeout"):
            found.append(
                _finding(
                    detector="missing_timeout",
                    category="latency",
                    confidence=0.74,
                    file=rel,
                    line=node.lineno,
                    title=f"`{name}` has no timeout",
                    detail=f"`{function or 'this call'}` can wait forever if the remote service stalls.",
                    evidence=_line(source, node.lineno),
                    function=function,
                    extra={"call": name},
                )
            )
        if retries < 8 and owner is not None and not _retry_decorator(owner) and not _in_loop(tree, node):
            retries += 1
            found.append(
                _finding(
                    detector="missing_retry",
                    category="defect",
                    confidence=0.46,
                    file=rel,
                    line=node.lineno,
                    title=f"`{name}` is not retried",
                    detail="The external call is not inside a retry loop or a retry decorator.",
                    evidence=_line(source, node.lineno),
                    function=function,
                    extra={"call": name},
                )
            )
    return found


def _owner_function(tree: ast.AST, target: ast.AST) -> ast.AST | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if child is target:
                    return node
    return None


def _is_fastapi(source: str) -> bool:
    lowered = source.lower()
    return "fastapi" in lowered or "apirouter" in lowered


def _blocking_and_routes(tree: ast.AST, source: str, rel: str) -> list[dict]:
    found: list[dict] = []
    missing_models = 0
    fastapi = _is_fastapi(source)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        route = _route_decorator(node)
        if (
            fastapi
            and route is not None
            and missing_models < 8
            and not _has_keyword(route, "response_model")
        ):
            missing_models += 1
            found.append(
                _finding(
                    detector="missing_response_model",
                    category="fastapi",
                    confidence=0.5,
                    file=rel,
                    line=route.lineno,
                    title=f"`{node.name}` has no response_model",
                    detail="The route does not declare the shape of its response.",
                    evidence=_line(source, route.lineno),
                    function=node.name,
                )
            )
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call) or child is route:
                continue
            called = _dotted(child.func)
            if called not in _BLOCKING and not called.startswith("requests."):
                continue
            routed = fastapi and route is not None
            titled = "fastapi_blocking_route" if routed else "blocking_in_async"
            category = "fastapi" if routed else "latency"
            found.append(
                _finding(
                    detector=titled,
                    category=category,
                    confidence=0.8,
                    file=rel,
                    line=child.lineno,
                    title=f"Async `{node.name}` calls blocking `{called}`",
                    detail="This call blocks the event loop. An async route should await a non-blocking client, or use asyncio.to_thread for a deliberate blocking boundary.",
                    evidence=_line(source, child.lineno),
                    function=node.name,
                    extra={"call": called},
                )
            )
    return found


def _dependencies(tree: ast.AST, source: str, rel: str) -> list[dict]:
    found: list[dict] = []
    for node in ast.walk(tree):
        if not _is_fastapi(source):
            return found
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or _route_decorator(node) is None:
            continue
        for default in node.args.defaults:
            if not isinstance(default, ast.Call):
                continue
            name = _dotted(default.func)
            if name.split(".")[-1] == "Depends":
                if default.args and isinstance(default.args[0], ast.Call):
                    found.append(
                        _finding(
                            detector="called_dependency",
                            category="fastapi",
                            confidence=0.84,
                            file=rel,
                            line=default.lineno,
                            title=f"`{node.name}` calls the dependency before Depends",
                            detail="Depends should receive the callable, not the result of calling it.",
                            evidence=_line(source, default.lineno),
                            function=node.name,
                        )
                    )
                continue
            if name.startswith("get_"):
                found.append(
                    _finding(
                        detector="missing_depends",
                        category="fastapi",
                        confidence=0.8,
                        file=rel,
                        line=default.lineno,
                        title=f"`{node.name}` calls `{name}` without Depends",
                        detail="FastAPI only injects the value when the default is wrapped in Depends.",
                        evidence=_line(source, default.lineno),
                        function=node.name,
                    )
                )
    return found


def _exceptions(tree: ast.AST, source: str, rel: str) -> list[dict]:
    found: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        bare = node.type is None
        broad = isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"}
        if not bare and not broad:
            continue
        swallowed = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
        if not bare and not swallowed:
            continue
        function = _enclosing_function(tree, node)
        title = "Exception is swallowed" if swallowed else "Bare except hides the failure"
        found.append(
            _finding(
                detector="swallowed_except",
                category="defect",
                confidence=0.76,
                file=rel,
                line=node.lineno,
                title=title,
                detail=f"`{function or 'this handler'}` catches a broad failure and does not name it.",
                evidence=_line(source, node.lineno),
                function=function,
                extra={"bare": bare},
            )
        )
    return found


def _weak_auth(tree: ast.AST, source: str, rel: str) -> list[dict]:
    found: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted(node.func)
        if "jwt" not in name.lower() and not name.endswith("decode"):
            continue
        function = _enclosing_function(tree, node)
        for keyword in node.keywords:
            if keyword.arg == "verify" and _is_false(keyword.value):
                found.append(_auth_finding(rel, source, node, function, "JWT signature verification is disabled"))
            if keyword.arg == "algorithms" and _contains_none(keyword.value):
                found.append(_auth_finding(rel, source, node, function, "JWT allows the none algorithm"))
            if keyword.arg == "options" and isinstance(keyword.value, ast.Dict):
                for key, value in zip(keyword.value.keys, keyword.value.values):
                    if isinstance(key, ast.Constant) and key.value == "verify_signature" and _is_false(value):
                        found.append(_auth_finding(rel, source, node, function, "JWT signature verification is disabled"))
    return found


def _auth_finding(rel: str, source: str, node: ast.Call, function: str | None, title: str) -> dict:
    return _finding(
        detector="weak_jwt",
        category="auth",
        confidence=0.86,
        file=rel,
        line=node.lineno,
        title=title,
        detail=f"`{function or 'this decode'}` accepts a token without checking its signature.",
        evidence=_line(source, node.lineno),
        function=function,
    )


def _is_false(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _contains_none(node: ast.AST) -> bool:
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return False
    return any(isinstance(item, ast.Constant) and item.value == "none" for item in node.elts)


def _sql(tree: ast.AST, source: str, rel: str) -> list[dict]:
    found: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        if _dotted(node.func).split(".")[-1] not in {"execute", "executemany", "executescript"}:
            continue
        query = node.args[0]
        interpolated = isinstance(query, ast.JoinedStr) or (
            isinstance(query, ast.BinOp) and isinstance(query.op, (ast.Mod, ast.Add))
        )
        formatted = isinstance(query, ast.Call) and _dotted(query.func).endswith(".format")
        if not interpolated and not formatted:
            continue
        function = _enclosing_function(tree, node)
        found.append(
            _finding(
                detector="sql_interpolation",
                category="security",
                confidence=0.82,
                file=rel,
                line=node.lineno,
                title="SQL is built with string interpolation",
                detail=f"`{function or 'this query'}` puts data into the SQL string instead of using parameters.",
                evidence=_line(source, node.lineno),
                function=function,
            )
        )
    return found


def _secrets(tree: ast.AST, source: str, rel: str) -> list[dict]:
    found: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
            continue
        if not isinstance(node.value.value, str) or len(node.value.value) < 6:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.lower() in _SECRET_NAMES:
                found.append(
                    _finding(
                        detector="hardcoded_secret",
                        category="security",
                        confidence=0.7,
                        file=rel,
                        line=node.lineno,
                        title=f"`{target.id}` is hardcoded",
                        detail="The secret is stored in source. Move it to an environment variable.",
                        evidence=_line(source, node.lineno),
                        function=_enclosing_function(tree, node),
                    )
                )
    return found


def _shell(tree: ast.AST, source: str, rel: str) -> list[dict]:
    found: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _dotted(node.func).split(".")[-1] not in {"run", "call", "check_call", "check_output", "Popen"}:
            continue
        if not any(keyword.arg == "shell" and _is_true(keyword.value) for keyword in node.keywords):
            continue
        found.append(
            _finding(
                detector="shell_true",
                category="security",
                confidence=0.8,
                file=rel,
                line=node.lineno,
                title="Subprocess runs through the shell",
                detail="shell=True lets metacharacters in the command string change what runs.",
                evidence=_line(source, node.lineno),
                function=_enclosing_function(tree, node),
            )
        )
    return found


def _is_true(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _resources(tree: ast.AST, source: str, rel: str) -> list[dict]:
    managed: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                managed.add(id(item.context_expr))
    closed: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "close":
            if isinstance(node.func.value, ast.Name):
                closed.add(node.func.value.id)
    found: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        if id(node.value) in managed or not _is_resource(node.value):
            continue
        if not node.targets or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if name in closed:
            continue
        kind = _dotted(node.value.func) or "open"
        found.append(
            _finding(
                detector="resource_leak",
                category="defect",
                confidence=0.73,
                file=rel,
                line=node.lineno,
                title=f"`{name}` is opened and never closed",
                detail=f"`{kind}` is not used as a context manager and `{name}.close()` is not called.",
                evidence=_line(source, node.lineno),
                function=_enclosing_function(tree, node),
                extra={"call": kind},
            )
        )
    return found


def _is_resource(node: ast.Call) -> bool:
    name = _dotted(node.func)
    return name == "open" or name.endswith(".open") or name.endswith("Session") or name.endswith(".Session")


def _query_loops(tree: ast.AST, source: str, rel: str) -> list[dict]:
    found: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.AsyncFor)):
            continue
        for child in ast.walk(node):
            if child is node or not isinstance(child, ast.Call):
                continue
            short = _dotted(child.func).split(".")[-1]
            if short not in _QUERY:
                continue
            function = _enclosing_function(tree, node)
            found.append(
                _finding(
                    detector="query_in_loop",
                    category="latency",
                    confidence=0.64,
                    file=rel,
                    line=child.lineno,
                    title=f"`{short}` runs inside a loop",
                    detail=f"`{function or 'this loop'}` can issue one query per item.",
                    evidence=_line(source, child.lineno),
                    function=function,
                    extra={"call": short},
                )
            )
            break
    return found
