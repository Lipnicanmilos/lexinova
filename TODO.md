# TODO

## Offline testovanie
- [x] Upraviť `app/static/sw.js`, aby offline nezabíjal `POST /api/v1/words/test/start` a `POST /api/v1/words/test/submit`.
- [x] Doplnit debug logy do `app/templates/test.html` pre cacheKey a množstvo slov v offline cache.

## Admin prístup
- [x] Pridať `ADMIN_EMAILS` do `app/services/runtime.py` (ENV zoznam admin emailov).
- [x] Upraviť `app/routers/admin.py`, aby guard používal `ADMIN_EMAILS` namiesto `is_plus`.
- [x] Upraviť `GET /admin` aby renderovalo `app/templates/admin.html`.
- [ ] Dopísať admin “možnosti meniť nastavenia” (edit používateľov/kategórií/plus) – aktuálne je implementovaný len zoznam používateľov (`/api/admin/users`).


