#!/usr/bin/env python3
from __future__ import annotations
from typing import Any, Dict

PRODUCTION_VERIFIED = "PRODUCTION_VERIFIED"
CANDIDATE = "CANDIDATE"
PREVIEW_ONLY = "PREVIEW_ONLY"

_REGISTRY: Dict[str, Dict[str, Any]] = {
    "VF-RP-2G-1C-BALANCED": {
        "state": PRODUCTION_VERIFIED,
        "auto_apply": True,
        "evidence": "P07_RESOURCE_CALIBRATION_VF_RP_2G_1C_BALANCED_20260926",
        "legacy_reference": "1C_2G_BALANCED_REFERENCE",
        "required_next_proof": None,
    },
    "VF-RP-4G-2C-BALANCED": {
        "state": CANDIDATE,
        "auto_apply": False,
        "evidence": "MACHINE_SYNTHETIC_BASELINE_ONLY",
        "legacy_reference": "2C_4G_BALANCED_CANDIDATE",
        "required_next_proof": "REAL_2C_4G_READONLY_CALIBRATION",
    },
}

def get_calibration(profile_id: str) -> Dict[str, Any]:
    item = _REGISTRY.get(profile_id)
    if item is None:
        return {
            "profile_id": profile_id,
            "state": PREVIEW_ONLY,
            "auto_apply": False,
            "evidence": None,
            "legacy_reference": None,
            "required_next_proof": "INDEPENDENT_REAL_CALIBRATION",
        }
    return {"profile_id": profile_id, **item}

def all_registered() -> Dict[str, Dict[str, Any]]:
    return {key: get_calibration(key) for key in sorted(_REGISTRY)}
