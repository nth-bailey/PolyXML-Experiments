from __future__ import annotations

import os
import sys
import time
import tempfile
import shutil
from typing import Tuple


def create_mock_schema_package(root_dir: str, class_count: int = 2_000) -> Tuple[str, str]:
    """Create a mock multi-module schema package containing class_count dataclasses.

    Returns:
        (eager_pkg_name, lazy_pkg_name) paths
    """
    eager_dir = os.path.join(root_dir, "eager_pkg")
    lazy_dir = os.path.join(root_dir, "lazy_pkg")
    os.makedirs(eager_dir, exist_ok=True)
    os.makedirs(lazy_dir, exist_ok=True)

    # 1. Generate 20 modules each containing 100 dataclasses
    num_modules = 20
    classes_per_mod = class_count // num_modules

    class_to_mod = {}

    for mod_idx in range(num_modules):
        mod_name = f"cluster_{mod_idx:02d}"
        code_lines = [
            "from __future__ import annotations",
            "from dataclasses import dataclass",
            "from typing import Optional, List",
            "",
        ]
        for c in range(classes_per_mod):
            c_name = f"NeTExEntity_{mod_idx}_{c}"
            class_to_mod[c_name] = mod_name
            code_lines.append(f"@dataclass(slots=True, kw_only=True)")
            code_lines.append(f"class {c_name}:")
            code_lines.append(f"    id: str = '{c_name}_default'")
            code_lines.append(f"    version: Optional[str] = '1'")
            code_lines.append(f"    tags: List[str] = None")
            code_lines.append("")

        content = "\n".join(code_lines)
        with open(os.path.join(eager_dir, f"{mod_name}.py"), "w") as f:
            f.write(content)
        with open(os.path.join(lazy_dir, f"{mod_name}.py"), "w") as f:
            f.write(content)

    # 2. Write eager __init__.py: imports every single class
    eager_init_lines = []
    for mod_idx in range(num_modules):
        mod_name = f"cluster_{mod_idx:02d}"
        eager_init_lines.append(f"from .{mod_name} import *")
    with open(os.path.join(eager_dir, "__init__.py"), "w") as f:
        f.write("\n".join(eager_init_lines))

    # 3. Write lazy __init__.py: uses PEP 562 __getattr__ dispatcher
    lazy_init_lines = [
        "import importlib",
        f"_CLASS_TO_MOD = {repr(class_to_mod)}",
        "",
        "def __getattr__(name: str):",
        "    if name in _CLASS_TO_MOD:",
        "        mod_name = _CLASS_TO_MOD[name]",
        "        mod = importlib.import_module(f'.{mod_name}', __name__)",
        "        cls = getattr(mod, name)",
        "        globals()[name] = cls",
        "        return cls",
        "    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')",
        "",
        "def __dir__():",
        "    return list(_CLASS_TO_MOD.keys()) + list(globals().keys())",
    ]
    with open(os.path.join(lazy_dir, "__init__.py"), "w") as f:
        f.write("\n".join(lazy_init_lines))

    return eager_dir, lazy_dir


def benchmark_class_loading(class_count: int = 2_000) -> dict:
    """Benchmark cold-start import time of eager vs lazy generated models."""
    temp_dir = tempfile.mkdtemp(prefix="netex_schema_bench_")
    sys.path.insert(0, temp_dir)

    try:
        eager_dir, lazy_dir = create_mock_schema_package(temp_dir, class_count=class_count)

        # Measure Eager Cold Start
        t0 = time.perf_counter()
        import eager_pkg  # triggers parsing of all modules
        t_eager_import = (time.perf_counter() - t0) * 1000.0

        # Access 1 entity in eager
        t0 = time.perf_counter()
        _ = getattr(eager_pkg, "NeTExEntity_0_0")
        t_eager_access = (time.perf_counter() - t0) * 1000.0

        # Measure Lazy Cold Start
        t0 = time.perf_counter()
        import lazy_pkg  # triggers ONLY __init__.py with dictionary
        t_lazy_import = (time.perf_counter() - t0) * 1000.0

        # Access 1 entity in lazy (triggers on-demand module import)
        t0 = time.perf_counter()
        cls = getattr(lazy_pkg, "NeTExEntity_0_0")
        t_lazy_first_access = (time.perf_counter() - t0) * 1000.0

        # Access second entity in same module (cached)
        t0 = time.perf_counter()
        _ = getattr(lazy_pkg, "NeTExEntity_0_1")
        t_lazy_second_access = (time.perf_counter() - t0) * 1000.0

        return {
            "class_count": class_count,
            "eager_import_ms": t_eager_import,
            "eager_access_ms": t_eager_access,
            "lazy_import_ms": t_lazy_import,
            "lazy_first_access_ms": t_lazy_first_access,
            "lazy_cached_access_ms": t_lazy_second_access,
            "speedup_factor": t_eager_import / max(t_lazy_import, 0.0001),
        }
    finally:
        sys.path.remove(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
