"""Command-line entry point for Tender Monitor.

Usage:
  python main.py --server [--host H --port P]   Start the local dashboard
  python main.py --scan                         Scan all enabled portals
  python main.py --scan-portal ID               Scan one portal
  python main.py --export                        Generate the Excel report
  python main.py --test-portal ID               Test a configured portal
  python main.py --status                        Print a status summary

Exit codes: 0 success, 1 completed with some failures, 2 fatal / bad usage.
"""
from __future__ import annotations

import argparse
import sys

import config
from utils.logging_setup import setup_logging, get_logger


def _init():
    setup_logging(console=True)
    config.ensure_directories()
    from database.database import get_db
    get_db()


def cmd_server(args):
    from app import run
    run(host=args.host, port=args.port)
    return 0


def cmd_scan(args):
    from services import scan_service
    summary = scan_service.scan_all_notify(trigger="cli")
    print("Scan complete: %d portal(s), %d successful, %d new, %d updated, %d documents"
          % (summary["portals"], summary["successful"], summary["new"],
             summary["updated"], summary["documents"]))
    if summary.get("excel_path"):
        print("Excel report: %s" % summary["excel_path"])
    result = summary.get("email_result") or {"sent": False, "reason": "not attempted"}
    if result.get("sent"):
        print("Summary email sent.")
    else:
        print("Summary email not sent (%s)." % result.get("reason"))
    return 0 if summary["successful"] == summary["portals"] else 1


def cmd_scan_portal(args):
    from services import scan_service
    result = scan_service.scan_portal(args.scan_portal, trigger="cli")
    print("Portal '%s': status=%s new=%d updated=%d existing=%d documents=%d"
          % (result["portal_name"], result["status"], result.get("new", 0),
             result.get("updated", 0), result.get("existing", 0), result.get("documents", 0)))
    return 0 if result["status"] in ("success", "baseline", "partial") else 1


def cmd_export(args):
    from reports import excel_exporter
    path = excel_exporter.generate_report()
    print("Excel report generated: %s" % path)
    return 0


def cmd_test_portal(args):
    from services import tender_service as ts
    from scraper import portal_detector
    portal = ts.get_portal(args.test_portal)
    if portal is None:
        print("Portal %s not found." % args.test_portal)
        return 2
    report = portal_detector.test_portal(portal["url"], browser_mode=portal.get("browser_mode", "headless"))
    print("Portal Test Result: %s" % portal["name"])
    print("URL: %s" % report["url"])
    for check in report["checks"]:
        print("  %-28s %s %s" % (check["name"] + ":", check["status"],
                                 ("- " + check["detail"]) if check["detail"] else ""))
    print("Automation Readiness: %s" % report["readiness"])
    return 0


def cmd_status(args):
    from services import tender_service as ts
    stats = ts.dashboard_stats()
    print("=== Tender Monitor Status ===")
    print("Portals configured : %d (healthy=%d, attention=%d)"
          % (stats["total_portals"], stats["portals_healthy"], stats["portals_attention"]))
    print("Tenders in database: %d (new=%d, updated=%d)"
          % (stats["total_tenders"], stats["new_tenders"], stats["updated_tenders"]))
    print("Documents downloaded: %d" % stats["documents_downloaded"])
    last = stats.get("last_scan")
    if last:
        print("Last scan: %s (%s) status=%s" % (last["portal_name"], last["finished_at"], last["status"]))
    print("\nPortals:")
    for p in ts.list_portals():
        print("  [%d] %-24s %-8s %-7s %s"
              % (p["id"], p["name"][:24], "enabled" if p["enabled"] else "disabled",
                 p["schedule_type"], p["url"]))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Tender Monitor - local tender monitoring tool")
    parser.add_argument("--server", action="store_true", help="Start the local web dashboard")
    parser.add_argument("--host", default=None, help="Server host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Server port (default 8000)")
    parser.add_argument("--scan", action="store_true", help="Scan all enabled portals")
    parser.add_argument("--scan-portal", type=int, metavar="ID", help="Scan a single portal by id")
    parser.add_argument("--export", action="store_true", help="Generate the Excel report")
    parser.add_argument("--test-portal", type=int, metavar="ID", help="Test a configured portal by id")
    parser.add_argument("--status", action="store_true", help="Print a status summary")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    _init()

    try:
        if args.server:
            return cmd_server(args)
        if args.scan:
            return cmd_scan(args)
        if args.scan_portal is not None:
            return cmd_scan_portal(args)
        if args.export:
            return cmd_export(args)
        if args.test_portal is not None:
            return cmd_test_portal(args)
        if args.status:
            return cmd_status(args)
    except KeyboardInterrupt:
        print("Interrupted.")
        return 2
    except Exception as exc:
        get_logger("app").error("Command failed: %s", exc)
        print("Error: %s" % exc)
        return 2

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
