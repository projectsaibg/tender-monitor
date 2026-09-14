"""FastAPI application: the local dashboard and JSON API.

Runs at http://127.0.0.1:8000 by default. Scan and TEST PORTAL work happens in
worker threads (Playwright uses a synchronous API that must not run on the
asyncio loop). Long scans are launched in a background thread so the UI stays
responsive; the dashboard polls /api/status.
"""
from __future__ import annotations

import threading

from fastapi import FastAPI, Request, Form
from fastapi.responses import (HTMLResponse, RedirectResponse, JSONResponse,
                               FileResponse)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config
from database.database import get_db
from services import tender_service as ts
from services import scan_service
from services import update_service
from scheduler.scheduler import get_scheduler
from utils.logging_setup import get_logger, setup_logging
from utils import security

log = get_logger("app")

templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


def _start_background(target, *args):
    if scan_service.scan_state().get("running"):
        return False
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()
    return True


def _base_context(request):
    sched = get_scheduler()
    return {
        "request": request,
        "app_title": config.APP_TITLE,
        "app_version": config.APP_VERSION,
        "scan_running": scan_service.scan_state().get("running"),
        "next_run": sched.next_run(),
        "author": config.APP_AUTHOR,
        "contact_email": config.APP_CONTACT_EMAIL,
        "contact_whatsapp": config.APP_CONTACT_WHATSAPP,
        "contact_whatsapp_link": config.APP_CONTACT_WHATSAPP_LINK,
        "repo_url": config.APP_REPO_URL,
        "app_license": config.APP_LICENSE,
        "update": update_service.state(),
    }


def create_app():
    setup_logging()
    config.ensure_directories()
    get_db()  # initialise schema

    app = FastAPI(title=config.APP_TITLE, version=config.APP_VERSION)
    app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

    @app.on_event("startup")
    def _startup():
        get_scheduler().start()
        update_service.check_in_background()
        log.info("%s %s started", config.APP_TITLE, config.APP_VERSION)

    @app.on_event("shutdown")
    def _shutdown():
        get_scheduler().shutdown()

    # --------------------------------------------------------------------- #
    # Dashboard
    # --------------------------------------------------------------------- #
    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        ctx = _base_context(request)
        ctx.update({
            "stats": ts.dashboard_stats(),
            "recent_scans": ts.list_scans(8),
            "notifications": ts.list_notifications(8),
            "portals": ts.list_portals(),
        })
        return templates.TemplateResponse(request, "dashboard.html", ctx)

    # --------------------------------------------------------------------- #
    # Portals
    # --------------------------------------------------------------------- #
    @app.get("/portals", response_class=HTMLResponse)
    def portals_page(request: Request):
        ctx = _base_context(request)
        sched = get_scheduler()
        portals = ts.list_portals()
        for p in portals:
            p["next_run"] = sched.portal_next_run(p["id"])
            p["tender_count"] = ts.count_tenders_for_portal(p["id"])
        ctx["portals"] = portals
        return templates.TemplateResponse(request, "portals.html", ctx)

    @app.get("/portals/new", response_class=HTMLResponse)
    def portal_new(request: Request):
        ctx = _base_context(request)
        ctx["portal"] = None
        return templates.TemplateResponse(request, "portal_form.html", ctx)

    @app.get("/portals/{portal_id}/edit", response_class=HTMLResponse)
    def portal_edit(request: Request, portal_id: int):
        ctx = _base_context(request)
        ctx["portal"] = ts.get_portal(portal_id)
        return templates.TemplateResponse(request, "portal_form.html", ctx)

    def _form_to_portal(form):
        data = {k: form.get(k) for k in form.keys()}
        for cb in ("enabled", "download_documents", "treat_first_scan_as_new"):
            data[cb] = "1" if form.get(cb) in ("on", "1", "true", "yes") else "0"
        follow = "1" if form.get("follow_detail") in ("on", "1", "true", "yes") else "0"
        only_matching = form.get("only_matching") in ("on", "1", "true", "yes")
        try:
            nic_max_orgs = int(form.get("nic_max_orgs") or 60)
        except (TypeError, ValueError):
            nic_max_orgs = 60
        nic_max_orgs = max(1, min(nic_max_orgs, 500))
        data["config_json"] = {"follow_detail": follow == "1",
                               "detail_limit": int(form.get("detail_limit") or 20),
                               "nic_max_orgs": nic_max_orgs,
                               "only_matching": only_matching}
        data["adapter"] = form.get("adapter") or "generic"
        return data

    @app.post("/portals")
    async def portal_create(request: Request):
        form = await request.form()
        portal_id = ts.create_portal(_form_to_portal(form))
        get_scheduler().reschedule_portal(portal_id)
        return RedirectResponse("/portals", status_code=303)

    @app.post("/portals/{portal_id}")
    async def portal_update(request: Request, portal_id: int):
        form = await request.form()
        ts.update_portal(portal_id, _form_to_portal(form))
        get_scheduler().reschedule_portal(portal_id)
        return RedirectResponse("/portals", status_code=303)

    @app.post("/portals/{portal_id}/delete")
    def portal_delete(portal_id: int):
        get_scheduler().remove_portal(portal_id)
        ts.delete_portal(portal_id)
        return RedirectResponse("/portals", status_code=303)

    @app.post("/portals/{portal_id}/clone")
    def portal_clone(portal_id: int):
        new_id = ts.clone_portal(portal_id)
        if not new_id:
            return RedirectResponse("/portals", status_code=303)
        get_scheduler().reschedule_portal(new_id)
        # Land on the clone's edit page so the user can change the name and URL.
        return RedirectResponse("/portals/%d/edit" % new_id, status_code=303)

    @app.post("/portals/{portal_id}/toggle")
    def portal_toggle(portal_id: int):
        portal = ts.get_portal(portal_id)
        if portal:
            ts.set_portal_enabled(portal_id, not portal.get("enabled"))
            get_scheduler().reschedule_portal(portal_id)
        return RedirectResponse("/portals", status_code=303)

    @app.post("/portals/{portal_id}/scan")
    def portal_scan(portal_id: int):
        _start_background(scan_service.scan_portal, portal_id, "manual")
        return RedirectResponse("/scans", status_code=303)

    @app.post("/scan/all")
    def scan_all_now():
        _start_background(scan_service.scan_all, "manual")
        return RedirectResponse("/", status_code=303)

    # --------------------------------------------------------------------- #
    # Tenders
    # --------------------------------------------------------------------- #
    def _build_search(q, archived):
        keys = ("portal_id", "keyword", "tender_id", "organisation", "location",
                "status", "relevance_band", "min_value", "max_value",
                "published_from", "published_to")
        filters = {k: q.get(k) or "" for k in keys}
        search = dict(filters)
        quick = ""
        if archived == 0 and q.get("new_today"):
            bounds = ts.local_today_bounds()
            search["status"] = filters["status"] = "new"
            search["first_seen_from"] = bounds["first_seen_from"]
            search["first_seen_to"] = bounds["first_seen_to"]
            quick = "new_today"
        elif archived == 0 and q.get("published_today"):
            bounds = ts.local_today_bounds()
            search["published_from"] = filters["published_from"] = bounds["date"]
            search["published_to"] = filters["published_to"] = bounds["date"]
            quick = "published_today"
        active = {k: v for k, v in search.items() if v}
        active["archived"] = archived
        return filters, active, quick

    def _notice_redirect(path, message):
        from urllib.parse import quote
        return RedirectResponse("%s?notice=%s" % (path, quote(message)), status_code=303)

    def _render_tenders(request, archived):
        filters, active, quick = _build_search(request.query_params, archived)
        results = ts.search_tenders(active, limit=2000)
        ctx = _base_context(request)
        ctx.update({"tenders": results, "filters": filters, "quick": quick,
                    "portals": ts.list_portals(), "count": len(results),
                    "mode": "archive" if archived else "active",
                    "notice": request.query_params.get("notice") or ""})
        return templates.TemplateResponse(request, "tenders.html", ctx)

    @app.get("/tenders", response_class=HTMLResponse)
    def tenders_page(request: Request):
        return _render_tenders(request, 0)

    @app.get("/archive", response_class=HTMLResponse)
    def archive_page(request: Request):
        return _render_tenders(request, 1)

    @app.post("/tenders/{tender_id}/archive")
    def tender_archive(tender_id: int):
        ts.set_tender_archived(tender_id, True)
        return RedirectResponse("/tenders", status_code=303)

    @app.post("/archive/{tender_id}/restore")
    def tender_restore(tender_id: int):
        ts.set_tender_archived(tender_id, False)
        return RedirectResponse("/archive", status_code=303)

    @app.post("/tenders/archive_reviewed")
    def tenders_archive_reviewed():
        n = ts.archive_existing()
        return _notice_redirect("/tenders", "Archived %d unchanged tender(s); New and "
                                "Updated ones were kept." % n)

    @app.post("/tenders/archive_all")
    def tenders_archive_all():
        n = ts.archive_matching({})
        return _notice_redirect("/tenders", "Archived %d tender(s). The active list is clear." % n)

    @app.post("/archive/restore_all")
    def archive_restore_all():
        n = ts.restore_matching({})
        return _notice_redirect("/archive", "Restored %d tender(s) to the active list." % n)

    @app.get("/tenders/{tender_id}", response_class=HTMLResponse)
    def tender_detail(request: Request, tender_id: int):
        tender = ts.get_tender(tender_id)
        ctx = _base_context(request)
        ctx.update({
            "tender": tender,
            "versions": ts.list_versions(tender_id) if tender else [],
            "documents": ts.documents_for_tender(tender_id) if tender else [],
        })
        return templates.TemplateResponse(request, "tender_detail.html", ctx)

    # --------------------------------------------------------------------- #
    # Scans
    # --------------------------------------------------------------------- #
    @app.get("/scans", response_class=HTMLResponse)
    def scans_page(request: Request):
        q = request.query_params
        ctx = _base_context(request)
        ctx["scans"] = ts.list_scans(200)
        selected = q.get("scan_id")
        if selected:
            ctx["selected_scan"] = ts.get_scan(int(selected))
            ctx["scan_errors"] = ts.scan_errors_for(int(selected))
        return templates.TemplateResponse(request, "scans.html", ctx)

    # --------------------------------------------------------------------- #
    # Settings
    # --------------------------------------------------------------------- #
    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request):
        ctx = _base_context(request)
        ctx["settings"] = ts.get_settings()
        return templates.TemplateResponse(request, "settings.html", ctx)

    @app.post("/settings")
    async def settings_save(request: Request):
        form = await request.form()
        data = {k: form.get(k) for k in form.keys()}
        for cb in ("smtp_use_tls", "notify_enabled", "notify_only_if_new",
                   "notify_only_high_relevance", "notify_only_errors",
                   "notify_attach_excel"):
            data[cb] = "1" if form.get(cb) in ("on", "1", "true", "yes") else "0"
        ts.save_settings(data)
        # Reapply timezone by restarting the scheduler.
        sched = get_scheduler()
        sched.shutdown()
        sched.start()
        return RedirectResponse("/settings", status_code=303)

    # --------------------------------------------------------------------- #
    # JSON API / actions
    # --------------------------------------------------------------------- #
    @app.post("/api/test-portal")
    def api_test_portal(url: str = Form(...), browser_mode: str = Form("headless")):
        # Sync endpoint -> runs in a worker thread, so Playwright is safe here.
        from scraper import portal_detector
        try:
            report = portal_detector.test_portal(url, browser_mode=browser_mode)
        except Exception as exc:
            return JSONResponse({"error": str(exc), "readiness": "SITE UNAVAILABLE",
                                 "checks": [], "url": url}, status_code=200)
        return JSONResponse(report)

    @app.get("/api/status")
    def api_status():
        return JSONResponse({
            "stats": _jsonable(ts.dashboard_stats()),
            "scan": scan_service.scan_state(),
            "next_run": get_scheduler().next_run(),
        })

    @app.post("/scheduler/pause")
    def scheduler_pause():
        get_scheduler().pause()
        return RedirectResponse("/", status_code=303)

    @app.post("/scheduler/resume")
    def scheduler_resume():
        get_scheduler().resume()
        return RedirectResponse("/", status_code=303)

    @app.get("/export")
    def export_excel():
        from reports import excel_exporter
        path = excel_exporter.generate_report()
        import os
        return FileResponse(
            path, filename=os.path.basename(path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.get("/downloads/open")
    def open_download(path: str):
        import os
        try:
            safe = security.safe_join(config.DOWNLOADS_DIR, os.path.relpath(path, config.DOWNLOADS_DIR))
        except Exception:
            return JSONResponse({"error": "Invalid path"}, status_code=400)
        if not os.path.exists(safe):
            return JSONResponse({"error": "File not found"}, status_code=404)
        return FileResponse(safe, filename=os.path.basename(safe))

    @app.get("/about", response_class=HTMLResponse)
    def about_page(request: Request):
        ctx = _base_context(request)
        ctx["update"] = update_service.state()
        return templates.TemplateResponse(request, "about.html", ctx)

    @app.post("/api/check-update")
    def api_check_update():
        return JSONResponse(_jsonable(update_service.check_for_update(force=True)))

    return app


def _jsonable(value):
    """Make dashboard stats JSON-serialisable (drop nested sqlite Row/None)."""
    import json
    return json.loads(json.dumps(value, default=str))


app = create_app()


def run(host=None, port=None):
    import uvicorn
    uvicorn.run(app, host=host or config.APP_HOST, port=port or config.APP_PORT, log_level="info")
