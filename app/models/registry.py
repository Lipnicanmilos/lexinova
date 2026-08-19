"""Načíta všetky modely naraz — pre skripty a jednorazové úlohy.

SQLAlchemy si pri zápise zoraďuje tabuľky podľa cudzích kľúčov a mapper si pri
prvom použití rozlúšti vzťahy podľa **názvu triedy**. Ak je načítaná len časť
modelov, obe veci padnú, a to až pri commite — čítanie prejde bez problému:

    NoReferencedTableError: … could not find table 'categories'
    InvalidRequestError: expression 'User' failed to locate a name

Aplikácia si modely registruje v `app/main.py`, ale skript nemá dôvod ťahať
celý FastAPI. Importuje si preto tento modul. Nič sa odtiaľto neimportuje späť,
takže nevzniká cyklus.

    import app.models.registry  # noqa: F401
"""
from app.models.category import Category  # noqa: F401
from app.models.demo_generation import DemoGeneration  # noqa: F401
from app.models.inquiry import Inquiry  # noqa: F401
from app.models.job_run import JobRun, JobRunHistory  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.school_class import ClassCategory, ClassMember, SchoolClass  # noqa: F401
from app.models.test_session import TestSession  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.word import Word  # noqa: F401
from app.models.word_level_event import WordLevelEvent  # noqa: F401
from app.models.word_progress import WordProgress  # noqa: F401
