"""In-application scheduling with APScheduler.

Portal schedules live in the database (schedule_type/run_time/day_of_week), so
jobs are rebuilt from the DB on start and survive restarts. This drives the
dashboard while the server is open; unattended runs are handled separately by
Windows Task Scheduler calling ``python main.py --scan``.
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from services import tender_service as ts
from utils.logging_setup import get_logger

log = get_logger("app")

_WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class SchedulerService:
    def __init__(self):
        self._sched = None

    def start(self):
        if self._sched is not None:
            return
        tz = ts.get_timezone_name()
        try:
            self._sched = BackgroundScheduler(timezone=tz)
        except Exception as exc:
            log.warning("Falling back to local timezone for scheduler: %s", exc)
            self._sched = BackgroundScheduler()
        self._sched.start()
        self.reload_all()
        log.info("Scheduler started (timezone=%s)", tz)

    def shutdown(self):
        if self._sched is not None:
            self._sched.shutdown(wait=False)
            self._sched = None

    @property
    def running(self):
        return self._sched is not None and self._sched.running

    def _job_id(self, portal_id):
        return "portal_%d" % portal_id

    def _parse_time(self, value):
        try:
            hh, mm = str(value or "07:00").split(":")[:2]
            return max(0, min(23, int(hh))), max(0, min(59, int(mm)))
        except Exception:
            return 7, 0

    def reload_all(self):
        if self._sched is None:
            return
        for portal in ts.list_portals():
            self.schedule_portal(portal)

    def schedule_portal(self, portal):
        if self._sched is None:
            return
        job_id = self._job_id(portal["id"])
        existing = self._sched.get_job(job_id)
        if existing:
            self._sched.remove_job(job_id)
        if not portal.get("enabled"):
            return
        stype = (portal.get("schedule_type") or "manual").lower()
        if stype not in ("daily", "weekly"):
            return  # manual: no automatic job
        hh, mm = self._parse_time(portal.get("run_time"))
        if stype == "daily":
            trigger = CronTrigger(hour=hh, minute=mm)
        else:
            dow = portal.get("day_of_week")
            name = _WEEKDAYS[dow] if isinstance(dow, int) and 0 <= dow <= 6 else "mon"
            trigger = CronTrigger(day_of_week=name, hour=hh, minute=mm)
        self._sched.add_job(
            self._run_job, trigger, id=job_id, args=[portal["id"]],
            replace_existing=True, misfire_grace_time=3600, coalesce=True,
            max_instances=1)
        log.info("Scheduled portal %s (%s %02d:%02d)", portal["name"], stype, hh, mm)

    def _run_job(self, portal_id):
        from services import scan_service
        try:
            scan_service.scan_portal(portal_id, trigger="scheduled")
        except Exception as exc:
            log.error("Scheduled scan failed for portal %s: %s", portal_id, exc)

    def reschedule_portal(self, portal_id):
        portal = ts.get_portal(portal_id)
        if portal:
            self.schedule_portal(portal)

    def remove_portal(self, portal_id):
        if self._sched is None:
            return
        job_id = self._job_id(portal_id)
        if self._sched.get_job(job_id):
            self._sched.remove_job(job_id)

    def pause(self):
        if self._sched:
            self._sched.pause()

    def resume(self):
        if self._sched:
            self._sched.resume()

    def next_run(self):
        if self._sched is None:
            return None
        times = [j.next_run_time for j in self._sched.get_jobs() if j.next_run_time]
        return min(times).isoformat() if times else None

    def portal_next_run(self, portal_id):
        if self._sched is None:
            return None
        job = self._sched.get_job(self._job_id(portal_id))
        return job.next_run_time.isoformat() if job and job.next_run_time else None

    def jobs(self):
        if self._sched is None:
            return []
        return [{"id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None}
                for j in self._sched.get_jobs()]


_service = SchedulerService()


def get_scheduler():
    return _service
