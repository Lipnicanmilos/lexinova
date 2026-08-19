"""Verzia aplikácie.

Formát `MAJOR.MINOR.BUILD`. **BUILD generuje git hook**, netreba ho písať ručne
— `.githooks/pre-commit` ho pred každým commitom prepíše na počet commitov v
histórii, takže s každým commitom stúpne o jeden a z čísla je vidno, ako ďaleko
je nasadená verzia od aktuálnej.

MAJOR a MINOR sa menia ručne, keď to dáva zmysel (väčšia funkcia, prelom).

Jednorazové zapnutie hooku po naklonovaní repozitára:

    git config core.hooksPath .githooks
"""

MAJOR_MINOR = "1.0"
BUILD = 400

VERSION = f"{MAJOR_MINOR}.{BUILD}"
