from app.database.connection import Base
from sqlalchemy import Column, Integer, SmallInteger, String, Date, DateTime, Index


class JobRun(Base):
    """Stav posledného behu denného jobu (lazy „anacron" scheduler).

    Jeden riadok = jeden registrovaný job. Cloud Run škáluje na nulu a beží vo
    viacerých inštanciách, takže in-process cron nie je spoľahlivý — namiesto
    toho sa pri spracovaní requestov skontroluje, či job dnes už bežal.

    Atomický `UPDATE` tohto riadku (v `scheduler._claim`) zabezpečuje, že job
    naprieč súbežnými inštanciami vykoná práve jedna — tá, ktorej UPDATE zmenil
    riadok.
    """
    __tablename__ = "job_runs"

    job_name = Column(String(64), primary_key=True)
    last_run_date = Column(Date, nullable=True)      # posledný deň (UTC), kedy job bežal
    last_run_at = Column(DateTime, nullable=True)    # presný čas posledného behu (UTC)
    last_status = Column(String(20), nullable=True)  # running / ok / error
    last_error = Column(String(500), nullable=True)  # skrátená chyba pri last_status='error'
    # Override cieľovej hodiny (UTC, 0–23) z admin panela; NULL = default z kódu.
    run_after_hour = Column(SmallInteger, nullable=True)


class JobRunHistory(Base):
    """História behov denných jobov (auto aj manuálne z admin panela).

    Jeden riadok = jeden beh. Rast tabuľky je zanedbateľný (pár jobov × 1 beh
    denne), preto sa zatiaľ nečistí."""
    __tablename__ = "job_run_history"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(64), nullable=False)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False)       # ok / error
    error = Column(String(500), nullable=True)
    triggered_by = Column(String(10), nullable=False, default="auto")  # auto / manual


Index("ix_job_run_history_job_started", JobRunHistory.job_name, JobRunHistory.started_at)
