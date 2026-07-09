"""Lazy „anacron" scheduler denných jobov pre Cloud Run.

Cloud Run uspáva inštancie a škáluje na nulu → in-process APScheduler/cron
nefunguje spoľahlivo (keď nikto nesurfuje, nič nebeží). Namiesto toho pri
spracovaní requestov lacno skontrolujeme, či denný job dnes už bežal — ak nie
(a je po jeho cieľovej hodine), dobehne sa dodatočne.

Vlastnosti:
  * **Dobiehanie zmeškaných behov** — ak deň prebehol bez behu, job sa spustí
    pri prvom requeste ďalší deň (joby musia byť idempotentné, viď register_job).
  * **Ochrana pred duplicitou naprieč inštanciami** — atomický UPDATE riadku
    `job_runs` (WHERE last_run_date < today): job vykoná len tá inštancia,
    ktorej UPDATE zmenil riadok.
  * **Lacný hook** — `maybe_run_due_jobs()` sa volá z middleware pri každom
    requeste, ale DB sa dotkne max. raz za `_CHECK_INTERVAL_S` na inštanciu.

Obmedzenie (akceptované): ak celý deň nepríde žiadny request, job dobehne až
pri prvej návšteve nasledujúci deň.
"""
import time
from datetime import date
from typing import Callable, Optional

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from starlette.concurrency import run_in_threadpool

from app.database.connection import SessionLocal
from app.models.job_run import JobRun, JobRunHistory
from app.services.runtime import logger
from app.utils import utcnow


class _Job:
    def __init__(self, name: str, func: Callable, run_after_hour: int):
        self.name = name
        self.func = func
        self.run_after_hour = run_after_hour


# Register zaregistrovaných denných jobov (naplní ho app/services/jobs.py).
_REGISTRY: list[_Job] = []


def register_job(name: str, func: Callable, run_after_hour: int = 3) -> None:
    """Zaregistruje denný job.

    `func(db)` dostane DB session a MUSÍ byť **idempotentný** — pri zmeškanom
    dni sa spustí dodatočne a spracuje aktuálny stav (nie N-krát za N dní).
    `run_after_hour` je hodina (UTC, 0–23), pred ktorou sa job v daný deň ešte
    nespustí — cieľové „nočné" okno, nech maintenance nebeží počas špičky.
    Registrácia je idempotentná (rovnaké meno sa nepridá dvakrát — reload/testy).
    """
    if any(j.name == name for j in _REGISTRY):
        return
    _REGISTRY.append(_Job(name, func, run_after_hour))


def get_registered_jobs() -> list:
    """Zoznam zaregistrovaných jobov (pre admin panel)."""
    return list(_REGISTRY)


def get_job(name: str) -> Optional[_Job]:
    return next((j for j in _REGISTRY if j.name == name), None)


def _get_or_create_row(db, name: str) -> JobRun:
    """Vráti riadok jobu; pri prvom behu ho vytvorí. Súbežný INSERT z inej
    inštancie zachytí IntegrityError → prečíta existujúci riadok."""
    row = db.query(JobRun).filter(JobRun.job_name == name).first()
    if row:
        return row
    row = JobRun(job_name=name)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # inú inštanciu predbehla — riadok už existuje
        row = db.query(JobRun).filter(JobRun.job_name == name).first()
    return row


def _claim(db, name: str, run_date: date) -> bool:
    """Atomicky si nárokuje beh jobu na `run_date`.

    UPDATE zmení riadok len ak job v tento deň ešte nebežal → medzi súbežnými
    inštanciami vyhrá práve jedna. True = táto inštancia si beh nárokovala."""
    changed = (
        db.query(JobRun)
        .filter(
            JobRun.job_name == name,
            or_(JobRun.last_run_date.is_(None), JobRun.last_run_date < run_date),
        )
        .update(
            {
                JobRun.last_run_date: run_date,
                JobRun.last_run_at: utcnow(),
                JobRun.last_status: "running",
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return bool(changed)


def _finish(db, name: str, status: str, error: Optional[str]) -> None:
    """Zapíše výsledok behu (ok / error) do riadku jobu."""
    try:
        db.query(JobRun).filter(JobRun.job_name == name).update(
            {
                JobRun.last_status: status,
                JobRun.last_run_at: utcnow(),
                JobRun.last_error: error,
            },
            synchronize_session=False,
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()


def _record_history(db, name: str, started, status: str, error: Optional[str],
                    triggered_by: str) -> None:
    """Pridá riadok do histórie behov; zlyhanie histórie nesmie nič zhodiť."""
    try:
        db.add(JobRunHistory(
            job_name=name,
            started_at=started,
            finished_at=utcnow(),
            status=status,
            error=error,
            triggered_by=triggered_by,
        ))
        db.commit()
    except SQLAlchemyError:
        db.rollback()


def _execute(db, job: _Job, triggered_by: str) -> tuple:
    """Vykoná job (claim už musí byť nastavený), zapíše výsledok + históriu.
    Chybu jobu zachytí a zaloguje ako ERROR (→ e-mail alert). Vráti
    (status, error)."""
    started = utcnow()
    logger.info("Job '%s' spustený (%s)", job.name, triggered_by)
    try:
        job.func(db)
        status, error = "ok", None
        logger.info("Job '%s' dokončený", job.name)
    except Exception as exc:  # noqa: BLE001 — job nesmie zhodiť volajúceho
        db.rollback()
        status, error = "error", str(exc)[:500]
        logger.error("Job '%s' zlyhal: %s", job.name, exc, exc_info=True)
    _finish(db, job.name, status, error)
    _record_history(db, job.name, started, status, error, triggered_by)
    return status, error


def run_due_jobs(session_factory: Optional[sessionmaker] = None) -> None:
    """Prejde registrované joby a dobehne tie, čo dnes ešte nebežali.

    Poradie na jeden job: kontrola cieľovej hodiny → atomický claim → beh →
    zápis výsledku. Chyba jobu sa zaloguje ako ERROR (spustí e-mail alert cez
    existujúci mechanizmus v runtime.py) a NIKDY nezhodí request. Claim ostáva
    pre daný deň nastavený aj po zlyhaní (žiadne retry storm-y ani opakované
    alerty) — job sa skúsi znova ďalší deň; keďže je idempotentný, dobehne."""
    if not _REGISTRY:
        return
    now = utcnow()
    today = now.date()
    db = (session_factory or SessionLocal)()
    try:
        for job in _REGISTRY:
            try:
                row = _get_or_create_row(db, job.name)
                # Admin override cieľovej hodiny má prednosť pred defaultom z kódu.
                hour = row.run_after_hour if row.run_after_hour is not None else job.run_after_hour
                if now.hour < hour:
                    continue  # cieľová hodina v tento deň ešte nenastala
                if not _claim(db, job.name, today):
                    continue  # dnes už bežal alebo ho zobrala iná inštancia
                _execute(db, job, "auto")
            except Exception as exc:  # noqa: BLE001 — scheduler nesmie zhodiť request
                db.rollback()
                logger.error("Scheduler: job '%s' — infra chyba: %s", job.name, exc,
                             exc_info=True)
    finally:
        db.close()


def force_run(name: str, session_factory: Optional[sessionmaker] = None) -> dict:
    """Manuálne spustenie jobu (admin panel) — beží hneď, bez ohľadu na hodinu
    a dnešný claim. Claim na dnešok si nastaví, takže auto-beh v ten deň už
    nenaskočí. Vráti {"status": ..., "error": ...}; KeyError ak job neexistuje."""
    job = get_job(name)
    if job is None:
        raise KeyError(name)
    db = (session_factory or SessionLocal)()
    try:
        _get_or_create_row(db, name)
        db.query(JobRun).filter(JobRun.job_name == name).update(
            {
                JobRun.last_run_date: utcnow().date(),
                JobRun.last_run_at: utcnow(),
                JobRun.last_status: "running",
            },
            synchronize_session=False,
        )
        db.commit()
        status, error = _execute(db, job, "manual")
        return {"status": status, "error": error}
    finally:
        db.close()


# --- Lacný hook pre middleware ---------------------------------------------
_CHECK_INTERVAL_S = 300  # DB kontrola max. raz za 5 min na inštanciu
_last_check_mono = 0.0


async def maybe_run_due_jobs() -> None:
    """Volá sa z middleware pri requeste. Väčšinou len porovná čas a hneď sa
    vráti; DB sa dotkne max. raz za `_CHECK_INTERVAL_S` na inštanciu. Samotnú
    (synchrónnu) DB prácu presunie mimo event-loopu do threadpoolu."""
    global _last_check_mono
    mono = time.monotonic()
    if mono - _last_check_mono < _CHECK_INTERVAL_S:
        return
    _last_check_mono = mono  # nastav PRED behom → súbežné requesty preskočia
    try:
        await run_in_threadpool(run_due_jobs)
    except Exception:  # noqa: BLE001 — scheduler nesmie zhodiť request
        logger.exception("Lazy scheduler: neočakávaná chyba pri kontrole jobov")
