"""In-application scheduler configuration."""
from scheduler.scheduler import SchedulerService
from services import tender_service as ts


def test_parse_time():
    svc = SchedulerService()
    assert svc._parse_time("07:30") == (7, 30)
    assert svc._parse_time("18:05") == (18, 5)
    assert svc._parse_time("bad") == (7, 0)


def test_daily_job_created(db):
    pid = ts.create_portal({"name": "Daily", "url": "https://x.gov.in",
                            "enabled": "1", "schedule_type": "daily", "run_time": "07:00"})
    svc = SchedulerService()
    svc.start()
    try:
        job = svc._sched.get_job(svc._job_id(pid))
        assert job is not None
        assert job.next_run_time is not None
        assert svc.next_run() is not None
    finally:
        svc.shutdown()


def test_manual_portal_has_no_job(db):
    pid = ts.create_portal({"name": "Manual", "url": "https://x.gov.in",
                            "enabled": "1", "schedule_type": "manual"})
    svc = SchedulerService()
    svc.start()
    try:
        assert svc._sched.get_job(svc._job_id(pid)) is None
    finally:
        svc.shutdown()


def test_weekly_job_created(db):
    pid = ts.create_portal({"name": "Weekly", "url": "https://x.gov.in",
                            "enabled": "1", "schedule_type": "weekly",
                            "run_time": "08:00", "day_of_week": 0})
    svc = SchedulerService()
    svc.start()
    try:
        assert svc._sched.get_job(svc._job_id(pid)) is not None
    finally:
        svc.shutdown()
