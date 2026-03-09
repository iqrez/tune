import json
import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.schemas import CalibrationSnapshot, VehicleProfile
from app.parsers.msq_parser import MsqParser


class ProjectManager:
    def __init__(self, base_dir: str, db_path: str, version_limit: int = 100) -> None:
        self.base_dir = base_dir
        self.projects_dir = os.path.join(base_dir, "projects")
        self.db_path = db_path
        self.version_limit = max(10, int(version_limit))
        self.current_file = os.path.join(self.projects_dir, ".current_project.json")
        os.makedirs(self.projects_dir, exist_ok=True)
        self._migrate_db()
        self._ensure_default_project()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _migrate_db(self) -> None:
        conn = self._connect()
        try:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(snapshots)").fetchall()]
            if "project_id" not in cols:
                conn.execute("ALTER TABLE snapshots ADD COLUMN project_id TEXT DEFAULT 'untitled'")
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    def _ensure_default_project(self) -> None:
        current = self.get_current_project_name()
        if current:
            return
        self.create_project("Untitled", profile_json={"vehicle_id": "untitled"})
        self.switch_project("untitled")

    def _safe_name(self, name: str) -> str:
        raw = (name or "untitled").strip().lower()
        clean = "".join(ch for ch in raw if ch.isalnum() or ch in ("_", "-", " ")).strip()
        clean = clean.replace(" ", "_")
        return clean or "untitled"

    def _project_path(self, name: str) -> str:
        return os.path.join(self.projects_dir, self._safe_name(name))

    def _manifest_path(self, project_name: str) -> str:
        return os.path.join(self._project_path(project_name), "manifest.json")

    def _versions_dir(self, project_name: str) -> str:
        return os.path.join(self._project_path(project_name), "versions")

    def _tables_dir(self, project_name: str) -> str:
        return os.path.join(self._project_path(project_name), "tables")

    def _dashboards_dir(self, project_name: str) -> str:
        return os.path.join(self._project_path(project_name), "dashboards")

    def _datalogs_dir(self, project_name: str) -> str:
        return os.path.join(self._project_path(project_name), "datalogs")

    def _snapshots_db_path(self, project_name: str) -> str:
        return os.path.join(self._project_path(project_name), "snapshots.db")

    def get_current_project_name(self) -> str:
        if not os.path.exists(self.current_file):
            return ""
        try:
            with open(self.current_file, "r", encoding="utf-8") as f:
                return str((json.load(f) or {}).get("name", "")).strip()
        except Exception:
            return ""

    def _set_current_project_name(self, name: str) -> None:
        with open(self.current_file, "w", encoding="utf-8") as f:
            json.dump({"name": self._safe_name(name), "updated_at": time.time()}, f, indent=2)

    def _load_manifest(self, project_name: str) -> Dict[str, Any]:
        mp = self._manifest_path(project_name)
        if not os.path.exists(mp):
            return {
                "name": self._safe_name(project_name),
                "display_name": project_name,
                "created_at": time.time(),
                "updated_at": time.time(),
                "versions": [],
                "archived_versions": [],
                "profile_json": {},
            }
        try:
            with open(mp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
        except Exception:
            return {"name": self._safe_name(project_name), "versions": []}

    def _save_manifest(self, project_name: str, manifest: Dict[str, Any]) -> None:
        manifest["updated_at"] = time.time()
        with open(self._manifest_path(project_name), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def list_projects(self) -> Dict[str, Any]:
        projects = []
        current = self.get_current_project_name()
        for name in sorted(os.listdir(self.projects_dir)):
            p = os.path.join(self.projects_dir, name)
            if not os.path.isdir(p):
                continue
            if name.startswith("."):
                continue
            manifest = self._load_manifest(name)
            versions = manifest.get("versions", [])
            projects.append(
                {
                    "name": name,
                    "display_name": manifest.get("display_name", name),
                    "versions": len(versions),
                    "last_change": manifest.get("updated_at", 0),
                    "profile_json": manifest.get("profile_json", {}),
                }
            )
        return {"projects": projects, "current_project": current}

    def create_project(self, name: str, profile_json: Dict[str, Any], import_msq_path: Optional[str] = None) -> Dict[str, Any]:
        safe = self._safe_name(name)
        base = safe
        idx = 2
        while os.path.exists(self._project_path(safe)):
            safe = f"{base}_{idx}"
            idx += 1

        p = self._project_path(safe)
        os.makedirs(p, exist_ok=True)
        os.makedirs(self._versions_dir(safe), exist_ok=True)
        os.makedirs(self._tables_dir(safe), exist_ok=True)
        os.makedirs(self._dashboards_dir(safe), exist_ok=True)
        os.makedirs(self._datalogs_dir(safe), exist_ok=True)

        manifest = {
            "name": safe,
            "display_name": name or safe,
            "created_at": time.time(),
            "updated_at": time.time(),
            "versions": [],
            "archived_versions": [],
            "profile_json": profile_json or {},
        }
        self._save_manifest(safe, manifest)

        if import_msq_path and os.path.exists(import_msq_path):
            try:
                with open(import_msq_path, "rb") as f:
                    content = f.read()
                parser = MsqParser(content=content)
                snap = parser.extract_calibration()
                self.record_restore_point(safe, "veTable1", snap.fuel_table, snap.axes.get("rpm", []), snap.axes.get("map_kpa", []), source="import")
            except Exception:
                pass

        self.switch_project(safe)
        return {"status": "created", "name": safe}

    def switch_project(self, name: str) -> Dict[str, Any]:
        safe = self._safe_name(name)
        if not os.path.isdir(self._project_path(safe)):
            raise FileNotFoundError("Project not found")
        # Simple lock marker to help shared-folder workflows.
        lock_path = os.path.join(self._project_path(safe), ".lock")
        with open(lock_path, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "timestamp": time.time()}, f)
        self._set_current_project_name(safe)
        return {"status": "switched", "name": safe}

    def archive_project(self, name: str) -> Dict[str, Any]:
        safe = self._safe_name(name)
        src = self._project_path(safe)
        if not os.path.isdir(src):
            raise FileNotFoundError("Project not found")
        archived = os.path.join(self.projects_dir, f"{safe}_archived_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
        shutil.move(src, archived)
        return {"status": "archived", "from": safe, "to": os.path.basename(archived)}

    def delete_project(self, name: str) -> Dict[str, Any]:
        safe = self._safe_name(name)
        path = self._project_path(safe)
        if not os.path.isdir(path):
            raise FileNotFoundError("Project not found")
        shutil.rmtree(path, ignore_errors=True)
        if self.get_current_project_name() == safe:
            self._set_current_project_name("untitled")
        return {"status": "deleted", "name": safe}

    def record_restore_point(
        self,
        project_name: str,
        table_name: str,
        data: List[List[float]],
        rpm_axis: List[float],
        map_axis: List[float],
        source: str = "save",
    ) -> Dict[str, Any]:
        safe = self._safe_name(project_name)
        manifest = self._load_manifest(safe)
        versions = manifest.get("versions", [])
        next_num = (max([int(v.get("version", 0) or 0) for v in versions]) + 1) if versions else 1

        rows = len(data)
        cols = len(data[0]) if rows else 0
        zeros = [[0.0 for _ in range(cols)] for _ in range(rows)]

        if table_name == "veTable1":
            fuel_table, ign_table, boost_table = data, zeros, zeros
        elif table_name == "ignitionTable1":
            fuel_table, ign_table, boost_table = zeros, data, zeros
        elif table_name == "boostTable1":
            fuel_table, ign_table, boost_table = zeros, zeros, data
        else:
            fuel_table, ign_table, boost_table = data, zeros, zeros

        snap = CalibrationSnapshot(
            axes={"rpm": rpm_axis or [500 + i * 500 for i in range(cols)], "map_kpa": map_axis or [30 + i * 15 for i in range(rows)]},
            fuel_table=fuel_table,
            ignition_table=ign_table,
            boost_table=boost_table,
            metadata={"source": source, "project": safe, "table": table_name},
        )
        content = MsqParser.export_msq(snap)

        version_name = f"tune_v{next_num}.msq"
        path = os.path.join(self._versions_dir(safe), version_name)
        with open(path, "wb") as f:
            f.write(content)

        summary = self._version_summary(versions[-1] if versions else None, data)
        entry = {
            "version": next_num,
            "filename": version_name,
            "table_name": table_name,
            "timestamp": time.time(),
            "summary": summary,
        }
        versions.append(entry)
        manifest["versions"] = versions
        self._trim_versions(safe, manifest)
        self._save_manifest(safe, manifest)
        return {"status": "version_saved", "entry": entry}

    def _version_summary(self, prev_entry: Optional[Dict[str, Any]], new_data: List[List[float]]) -> str:
        if not prev_entry:
            return "v1 initial save"
        # Lightweight summary without fully parsing previous matrix.
        return "Table update saved"

    def _trim_versions(self, project_name: str, manifest: Dict[str, Any]) -> None:
        versions = manifest.get("versions", [])
        if len(versions) <= self.version_limit:
            return
        archive_dir = os.path.join(self._versions_dir(project_name), "archive")
        os.makedirs(archive_dir, exist_ok=True)
        while len(versions) > self.version_limit:
            old = versions.pop(0)
            src = os.path.join(self._versions_dir(project_name), old.get("filename", ""))
            if os.path.exists(src):
                shutil.move(src, os.path.join(archive_dir, os.path.basename(src)))
            manifest.setdefault("archived_versions", []).append(old)
        manifest["versions"] = versions

    def compare_versions(self, project_name: str, version1: int, version2: int, table_name: str = "veTable1") -> Dict[str, Any]:
        safe = self._safe_name(project_name)
        manifest = self._load_manifest(safe)
        versions = manifest.get("versions", [])

        v1 = next((v for v in versions if int(v.get("version", 0)) == int(version1)), None)
        v2 = next((v for v in versions if int(v.get("version", 0)) == int(version2)), None)
        if not v1 or not v2:
            raise FileNotFoundError("Version not found")

        t1 = self._load_table_from_version(safe, v1.get("filename"), table_name)
        t2 = self._load_table_from_version(safe, v2.get("filename"), table_name)

        rows = min(len(t1), len(t2))
        cols = min(len(t1[0]) if rows else 0, len(t2[0]) if rows else 0)
        delta = [[0.0 for _ in range(cols)] for _ in range(rows)]
        changed = 0
        for r in range(rows):
            for c in range(cols):
                d = float(t2[r][c]) - float(t1[r][c])
                delta[r][c] = round(d, 5)
                if abs(d) > 1e-9:
                    changed += 1

        return {
            "project": safe,
            "version1": v1,
            "version2": v2,
            "table_name": table_name,
            "left": t1,
            "right": t2,
            "delta": delta,
            "changed_cells": changed,
        }

    def _load_table_from_version(self, project_name: str, filename: str, table_name: str) -> List[List[float]]:
        path = os.path.join(self._versions_dir(project_name), filename)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "rb") as f:
                content = f.read()
            parser = MsqParser(content=content)
            snap = parser.extract_calibration()
            if table_name == "veTable1":
                return snap.fuel_table
            if table_name == "ignitionTable1":
                return snap.ignition_table
            if table_name == "boostTable1":
                return snap.boost_table
            return snap.fuel_table
        except Exception:
            return []

    def rollback(self, project_name: str, version: int, table_name: str = "veTable1") -> Dict[str, Any]:
        safe = self._safe_name(project_name)
        manifest = self._load_manifest(safe)
        versions = manifest.get("versions", [])
        entry = next((v for v in versions if int(v.get("version", 0)) == int(version)), None)
        if not entry:
            raise FileNotFoundError("Version not found")
        table = self._load_table_from_version(safe, entry.get("filename"), table_name)
        if not table:
            raise ValueError("Version is corrupted or unreadable")
        return {
            "status": "rollback_ready",
            "project": safe,
            "version": version,
            "table_name": table_name,
            "data": table,
            "entry": entry,
        }

    def export_project_zip(self, project_name: str) -> str:
        safe = self._safe_name(project_name)
        root = self._project_path(safe)
        if not os.path.isdir(root):
            raise FileNotFoundError("Project not found")
        fd, zip_path = tempfile.mkstemp(prefix=f"{safe}_", suffix=".zip")
        os.close(fd)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for base, _, files in os.walk(root):
                for fn in files:
                    fp = os.path.join(base, fn)
                    rel = os.path.relpath(fp, root)
                    z.write(fp, arcname=os.path.join(safe, rel))
        return zip_path

    def import_project_zip(self, zip_path: str) -> Dict[str, Any]:
        if not os.path.exists(zip_path):
            raise FileNotFoundError("Zip not found")
        with zipfile.ZipFile(zip_path, "r") as z:
            top_dirs = sorted(set(p.split("/")[0] for p in z.namelist() if "/" in p))
            if not top_dirs:
                raise ValueError("Invalid project zip")
            root_name = self._safe_name(top_dirs[0])
            target = root_name
            idx = 2
            while os.path.exists(self._project_path(target)):
                target = f"{root_name}_{idx}"
                idx += 1
            extract_to = self._project_path(target)
            os.makedirs(extract_to, exist_ok=True)
            z.extractall(self.projects_dir)
            src = self._project_path(root_name)
            if src != extract_to and os.path.exists(src):
                shutil.move(src, extract_to)
        return {"status": "imported", "name": target}

    def history(self, project_name: str) -> List[Dict[str, Any]]:
        manifest = self._load_manifest(project_name)
        versions = manifest.get("versions", [])
        return sorted(versions, key=lambda x: float(x.get("timestamp", 0)), reverse=True)

    def file_tree(self, project_name: str) -> List[Dict[str, Any]]:
        safe = self._safe_name(project_name)
        root = self._project_path(safe)
        out = []
        for base, dirs, files in os.walk(root):
            rel_base = os.path.relpath(base, root)
            for d in dirs:
                out.append({"type": "dir", "path": os.path.join(rel_base, d).replace("\\", "/")})
            for f in files:
                out.append({"type": "file", "path": os.path.join(rel_base, f).replace("\\", "/")})
        out.sort(key=lambda x: x["path"])
        return out
