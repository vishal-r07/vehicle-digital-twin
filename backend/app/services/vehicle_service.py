"""
============================================================================
AutoTwin AI - Vehicle Service
============================================================================
Manages vehicle plugins: discovery, loading, selection, and configuration.

Responsibilities:
  - Scan vehicles/ directory for plugins
  - Parse vehicle.json metadata
  - Load DBC files and fault rules per vehicle
  - Manage active vehicle selection
  - Provide vehicle data to API endpoints
  - Coordinate with CAN parser and fault engine on vehicle switch

Plugin Directory Structure:
  vehicles/
  ├── _registry.json
  ├── toyota_corolla_2020/
  │   ├── vehicle.json
  │   ├── can_signals.dbc
  │   ├── fault_rules.yaml
  │   ├── dashboard_layout.json
  │   ├── 3d_model.glb
  │   └── subsystem_map.json
  └── generic_obd2/
      └── ...

Usage:
    service = VehicleService(settings.vehicle)
    count = service.load_registry()
    service.select_vehicle("toyota_corolla_2020")
============================================================================
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger

from app.config import VehicleSettings
from app.core.constants import EventType
from app.core.event_bus import EventBus
from app.core.exceptions import VehicleNotFoundError, VehiclePluginError


# ============================================================================
# VEHICLE SERVICE
# ============================================================================


class VehicleService:
    """
    Manages vehicle plugin lifecycle.

    Handles discovery, validation, selection, and data access
    for all registered vehicle plugins.
    """

    def __init__(self, settings: VehicleSettings, event_bus: Optional[EventBus] = None):
        self._settings = settings
        self._event_bus = event_bus

        # Registry
        self._vehicles: Dict[str, Dict[str, Any]] = {}
        self._active_slug: Optional[str] = None

        # Paths
        self._plugins_dir = Path(settings.plugins_dir)
        self._registry_path = self._plugins_dir / settings.registry_file

        logger.info(f"VehicleService: initialized (plugins_dir={self._plugins_dir})")

    # ========================================================================
    # REGISTRY LOADING
    # ========================================================================

    def load_registry(self) -> int:
        """
        Load the vehicle registry from disk.

        Scans the plugins directory and loads all vehicle.json files.

        Returns:
            Number of vehicles loaded.
        """
        self._vehicles.clear()

        # Try _registry.json first
        if self._registry_path.exists():
            self._load_registry_file()
        else:
            # Fallback: scan directories
            self._scan_plugins_directory()

        # If still empty, create default generic vehicle
        if not self._vehicles:
            self._create_default_vehicle()

        logger.info(f"VehicleService: loaded {len(self._vehicles)} vehicle(s)")
        return len(self._vehicles)

    def _load_registry_file(self) -> None:
        """Load vehicles from _registry.json."""
        try:
            with open(self._registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)

            for entry in registry.get("vehicles", []):
                slug = entry.get("slug")
                if not slug:
                    continue

                vehicle_dir = self._plugins_dir / slug
                if not vehicle_dir.exists():
                    logger.warning(f"VehicleService: directory missing for '{slug}'")
                    continue

                vehicle_data = self._load_vehicle_directory(vehicle_dir, entry)
                if vehicle_data:
                    self._vehicles[slug] = vehicle_data

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"VehicleService: registry load error: {e}")
            self._scan_plugins_directory()

    def _scan_plugins_directory(self) -> None:
        """Scan plugins directory for vehicle.json files."""
        if not self._plugins_dir.exists():
            logger.warning(f"VehicleService: plugins directory not found: {self._plugins_dir}")
            return

        for item in self._plugins_dir.iterdir():
            if not item.is_dir():
                continue
            if item.name.startswith("_") or item.name.startswith("."):
                continue

            vehicle_json = item / "vehicle.json"
            if vehicle_json.exists():
                vehicle_data = self._load_vehicle_directory(item)
                if vehicle_data:
                    self._vehicles[item.name] = vehicle_data

    def _load_vehicle_directory(
        self, directory: Path, registry_entry: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Load and validate a single vehicle plugin directory."""
        slug = directory.name
        vehicle_json = directory / "vehicle.json"

        try:
            # Load vehicle.json
            if vehicle_json.exists():
                with open(vehicle_json, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            else:
                metadata = registry_entry or {}

            # Build complete vehicle data
            vehicle_data = {
                "slug": slug,
                "name": metadata.get("name", slug.replace("_", " ").title()),
                "make": metadata.get("make", "Unknown"),
                "model": metadata.get("model", "Unknown"),
                "year": metadata.get("year"),
                "category": metadata.get("category", "sedan"),
                "engine_type": metadata.get("engine_type", ""),
                "transmission_type": metadata.get("transmission_type", ""),
                "fuel_type": metadata.get("fuel_type", "gasoline"),
                "is_active": False,
                "path": str(directory),
                # File paths
                "dbc_path": str(directory / "can_signals.dbc") if (directory / "can_signals.dbc").exists() else None,
                "fault_rules_path": str(directory / "fault_rules.yaml") if (directory / "fault_rules.yaml").exists() else None,
                "model_3d_path": str(directory / "3d_model.glb") if (directory / "3d_model.glb").exists() else None,
                "dashboard_layout_path": str(directory / "dashboard_layout.json") if (directory / "dashboard_layout.json").exists() else None,
                "subsystem_map_path": str(directory / "subsystem_map.json") if (directory / "subsystem_map.json").exists() else None,
                # Flags
                "has_dbc": (directory / "can_signals.dbc").exists(),
                "has_fault_rules": (directory / "fault_rules.yaml").exists(),
                "has_3d_model": (directory / "3d_model.glb").exists(),
            }

            return vehicle_data

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"VehicleService: error loading '{slug}': {e}")
            return None

    def _create_default_vehicle(self) -> None:
        """Create a default generic vehicle when no plugins exist."""
        self._vehicles["generic_obd2"] = {
            "slug": "generic_obd2",
            "name": "Generic OBD-II Vehicle",
            "make": "Generic",
            "model": "OBD-II",
            "year": None,
            "category": "sedan",
            "engine_type": "Unknown",
            "transmission_type": "Unknown",
            "fuel_type": "gasoline",
            "is_active": False,
            "path": "",
            "dbc_path": None,
            "fault_rules_path": None,
            "model_3d_path": None,
            "dashboard_layout_path": None,
            "subsystem_map_path": None,
            "has_dbc": False,
            "has_fault_rules": False,
            "has_3d_model": False,
        }
        logger.info("VehicleService: created default generic vehicle")

    # ========================================================================
    # VEHICLE SELECTION
    # ========================================================================

    def select_vehicle(self, slug: str) -> Dict[str, Any]:
        """
        Select a vehicle as the active digital twin.

        Args:
            slug: Vehicle slug identifier

        Returns:
            Vehicle data dictionary

        Raises:
            VehicleNotFoundError: If slug doesn't exist
        """
        if slug not in self._vehicles:
            raise VehicleNotFoundError(slug)

        # Deactivate previous
        if self._active_slug and self._active_slug in self._vehicles:
            self._vehicles[self._active_slug]["is_active"] = False

        # Activate new
        self._vehicles[slug]["is_active"] = True
        self._active_slug = slug

        logger.info(f"VehicleService: selected '{slug}'")
        return self._vehicles[slug]

    def get_active_slug(self) -> Optional[str]:
        """Get slug of currently active vehicle."""
        return self._active_slug

    def get_active_vehicle(self) -> Optional[Dict[str, Any]]:
        """Get the active vehicle data."""
        if self._active_slug:
            return self._vehicles.get(self._active_slug)
        return None

    # ========================================================================
    # VEHICLE DATA ACCESS
    # ========================================================================

    def list_all(self) -> List[Dict[str, Any]]:
        """List all registered vehicles (summary format)."""
        result = []
        for slug, data in self._vehicles.items():
            result.append({
                "id": slug,
                "slug": slug,
                "name": data["name"],
                "make": data["make"],
                "model": data["model"],
                "year": data.get("year"),
                "category": data.get("category"),
                "is_active": data.get("is_active", False),
            })
        return result

    def get_vehicle(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get complete vehicle data by slug."""
        return self._vehicles.get(slug)

    def get_vehicle_signals(self, slug: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get CAN signal definitions for a vehicle.

        Reads from the vehicle's DBC file if available.
        """
        vehicle = self._vehicles.get(slug)
        if not vehicle:
            return None

        dbc_path = vehicle.get("dbc_path")
        if not dbc_path or not Path(dbc_path).exists():
            # Return default Phase 1 signals
            from app.can.signal_definitions import Phase1Signals
            signals = Phase1Signals.get_all()
            return [
                {
                    "name": name,
                    "can_id": config.can_id,
                    "unit": config.unit,
                    "min": config.min_value,
                    "max": config.max_value,
                    "frequency_hz": config.expected_frequency_hz,
                }
                for name, config in signals.items()
            ]

        # Load from DBC
        try:
            from app.can.dbc_loader import DBCParser
            parser = DBCParser(dbc_path)
            dbc = parser.load()

            signals = []
            for msg_id, msg in dbc.messages.items():
                for sig_name, sig in msg.signals.items():
                    signals.append({
                        "name": sig_name,
                        "can_id": msg_id,
                        "unit": sig.unit,
                        "min": sig.min_value,
                        "max": sig.max_value,
                        "factor": sig.factor,
                        "offset": sig.offset,
                    })
            return signals

        except Exception as e:
            logger.error(f"VehicleService: DBC load error for '{slug}': {e}")
            return None

    def get_vehicle_subsystems(self, slug: str) -> Optional[List[Dict[str, Any]]]:
        """Get subsystem definitions with 3D positions."""
        vehicle = self._vehicles.get(slug)
        if not vehicle:
            return None

        subsystem_map_path = vehicle.get("subsystem_map_path")
        if subsystem_map_path and Path(subsystem_map_path).exists():
            try:
                with open(subsystem_map_path, "r", encoding="utf-8") as f:
                    return json.load(f).get("subsystems", [])
            except Exception as e:
                logger.error(f"VehicleService: subsystem map error: {e}")

        # Default subsystems
        return [
            {"name": "engine", "display_name": "Engine", "position": [0, 0.3, 1.2], "color": "#ff6b35"},
            {"name": "brakes", "display_name": "Brakes", "position": [0, -0.3, 0], "color": "#ff3333"},
            {"name": "cooling", "display_name": "Cooling", "position": [0, 0.2, 2.0], "color": "#00ff88"},
            {"name": "battery", "display_name": "Battery", "position": [0.5, 0.2, 1.5], "color": "#eab308"},
            {"name": "transmission", "display_name": "Transmission", "position": [0, -0.2, 0.3], "color": "#6366f1"},
        ]

    def get_dashboard_layout(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get custom dashboard layout for a vehicle."""
        vehicle = self._vehicles.get(slug)
        if not vehicle:
            return None

        layout_path = vehicle.get("dashboard_layout_path")
        if layout_path and Path(layout_path).exists():
            try:
                with open(layout_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Default layout
        return {
            "primary_gauges": ["speed", "rpm"],
            "secondary_gauges": ["fuel", "temp", "battery"],
            "indicators": ["gear", "turn_signals", "doors", "headlights"],
        }

    # ========================================================================
    # PLUGIN VALIDATION
    # ========================================================================

    def validate_vehicle(self, slug: str) -> List[str]:
        """
        Validate a vehicle plugin.

        Returns:
            List of validation issues (empty if valid).
        """
        issues = []
        vehicle = self._vehicles.get(slug)

        if not vehicle:
            return [f"Vehicle '{slug}' not found"]

        if not vehicle.get("name"):
            issues.append("Missing vehicle name")

        if not vehicle.get("make"):
            issues.append("Missing vehicle make")

        # Check optional files
        if vehicle.get("dbc_path") and not Path(vehicle["dbc_path"]).exists():
            issues.append(f"DBC file not found: {vehicle['dbc_path']}")

        if vehicle.get("fault_rules_path") and not Path(vehicle["fault_rules_path"]).exists():
            issues.append(f"Fault rules file not found: {vehicle['fault_rules_path']}")

        return issues

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_vehicles": len(self._vehicles),
            "active_vehicle": self._active_slug,
            "plugins_dir": str(self._plugins_dir),
            "vehicles_with_dbc": sum(1 for v in self._vehicles.values() if v.get("has_dbc")),
            "vehicles_with_rules": sum(1 for v in self._vehicles.values() if v.get("has_fault_rules")),
            "vehicles_with_3d": sum(1 for v in self._vehicles.values() if v.get("has_3d_model")),
        }