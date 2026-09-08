#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from intrusion_scan import DiscoveryBudgetExceededError, UnsupportedWordPressLayoutError, discovery_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kv", action="store_true")
    args = parser.parse_args()
    try:
        report = discovery_report([])
    except UnsupportedWordPressLayoutError as error:
        if args.kv:
            print("P07_WP_DISCOVERY_STATUS=UNSAFE_LAYOUT")
            print("P07_WP_DISCOVERY_CLOUDPANEL_SITES=UNKNOWN")
            print("P07_WP_DISCOVERY_WORDPRESS_SITES=UNKNOWN")
        else:
            print(json.dumps({"status": "UNSAFE_LAYOUT", "error": str(error)}, ensure_ascii=False))
        return 20
    except DiscoveryBudgetExceededError as error:
        if args.kv:
            print("P07_WP_DISCOVERY_STATUS=BUDGET_EXCEEDED")
            print("P07_WP_DISCOVERY_CLOUDPANEL_SITES=UNKNOWN")
            print("P07_WP_DISCOVERY_WORDPRESS_SITES=UNKNOWN")
        else:
            print(json.dumps({"status": "BUDGET_EXCEEDED", "error": str(error)}, ensure_ascii=False))
        return 21

    count = len(report["wordpress_roots"])
    status = "READY" if count else "NO_WORDPRESS"
    if args.kv:
        print(f"P07_WP_DISCOVERY_STATUS={status}")
        print(f"P07_WP_DISCOVERY_SOURCE={report['source']}")
        print(f"P07_WP_DISCOVERY_CLOUDPANEL_SITES={report['cloudpanel_site_count']}")
        print(f"P07_WP_DISCOVERY_WORDPRESS_SITES={count}")
        return 0
    print(json.dumps({
        "status": status,
        "source": report["source"],
        "cloudpanel_site_count": report["cloudpanel_site_count"],
        "wordpress_site_count": count,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
