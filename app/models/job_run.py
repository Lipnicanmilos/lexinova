from app.database.connection import Base
from sqlalchemy import Column, String, Date, DateTime


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
