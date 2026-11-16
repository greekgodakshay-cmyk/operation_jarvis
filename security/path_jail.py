"""
Filesystem Sandboxing and Path Jailing for Windows Environments.
"""
import os
from pathlib import Path
from typing import List, Optional, Union
from config.settings import settings

class PathJailViolation(Exception):
    pass

class PathJail:
    def __init__(self, allowed_roots: Optional[List[Path]] = None, forbidden_dirs: Optional[List[str]] = None):
        self.allowed_roots = [r.resolve() for r in (allowed_roots or settings.allowed_workspace_roots)]
        self.forbidden_dirs = [os.path.normcase(os.path.abspath(f)) for f in (forbidden_dirs or settings.forbidden_directories)]

    def validate_path(self, target_path: Union[str, Path], allow_parent_must_exist: bool = True) -> Path:
        """
        Validates that a path:
        1. Resolves safely without directory traversal escapes.
        2. Is strictly within one of the allowed workspace roots.
        3. Does not reside inside any system-critical forbidden directories.
        """
        raw_path = Path(target_path)
        
        # If path doesn't exist yet (e.g. creating a new file), resolve parent
        try:
            if raw_path.exists():
                resolved = raw_path.resolve()
            else:
                # Check parent existence
                parent = raw_path.parent.resolve()
                resolved = parent / raw_path.name
        except Exception as e:
            raise PathJailViolation(f"Invalid path structure '{target_path}': {e}")

        norm_resolved = os.path.normcase(str(resolved))

        # Check forbidden directories first
        for forbidden in self.forbidden_dirs:
            if norm_resolved == forbidden or norm_resolved.startswith(forbidden + os.sep):
                raise PathJailViolation(
                    f"Access Denied: Path '{resolved}' falls within protected system directory '{forbidden}'."
                )

        # Check containment within at least one allowed root
        is_contained = False
        for root in self.allowed_roots:
            norm_root = os.path.normcase(str(root))
            if norm_resolved == norm_root or norm_resolved.startswith(norm_root + os.sep):
                is_contained = True
                break

        if not is_contained:
            raise PathJailViolation(
                f"Sandbox Boundary Violation: Path '{resolved}' is outside allowed workspaces: "
                f"{[str(r) for r in self.allowed_roots]}"
            )

        return resolved

# Type alias helper
from typing import Union
Union_Path = Union[str, Path]

# Global instance
path_jail = PathJail()
