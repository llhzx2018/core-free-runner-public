#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

SOURCE = Path(__file__).with_name('p05_phase3_browser_journey.py')
spec = importlib.util.spec_from_file_location('p05_phase3_browser_journey', SOURCE)
if spec is None or spec.loader is None:
    raise SystemExit('unable to load browser journey module')
journey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journey)


def xpath_literal(value: str) -> str:
    if "'" not in value:
        return "'" + value + "'"
    if '"' not in value:
        return '"' + value + '"'
    parts = value.split("'")
    return 'concat(' + ', "\'", '.join("'" + part + "'" for part in parts) + ')'


def button_with_text(session: str, label: str, scope: str = '') -> str:
    root = scope if scope else ''
    literal = xpath_literal(label)
    xpath = f"{root}//button[normalize-space(.)={literal}]" if root else f"//button[normalize-space(.)={literal}]"
    return journey.find(session, 'xpath', xpath)


def button_contains(session: str, label: str, scope: str = '') -> str:
    root = scope if scope else ''
    literal = xpath_literal(label)
    xpath = f"{root}//button[contains(normalize-space(.), {literal})]" if root else f"//button[contains(normalize-space(.), {literal})]"
    return journey.find(session, 'xpath', xpath)


journey.button_with_text = button_with_text
journey.button_contains = button_contains
journey.main()
