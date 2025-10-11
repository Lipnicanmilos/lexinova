# Oprava Google OAuth prihlásenia

## Informácie zhromaždené
- Aplikácia FastAPI s Google OAuth pomocou authlib.
- Nekonzistencia v hashovaní hesiel: auth_service používa bcrypt, main.py argon2.
- Callback nastaví session a presmeruje na auth-callback.html, ktoré nastaví localStorage a presmeruje na dashboard.
- Dashboard kontroluje session['user'].
- PHP súbory sú pravdepodobne nepoužívané.

## Plán opravy
1. Opraviť nekonzistenciu hashovania hesiel v main.py použitím auth_service funkcií namiesto argon2.
2. Pridať logovanie do google_callback v main.py na debugovanie chýb.
3. Skontrolovať .env súbor pre správne hodnoty GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, SESSION_SECRET.
4. Overiť, že redirect URI v Google Console zodpovedá nastaveniu.
5. Otestovať prihlásenie cez Google.

## Nasledujúce kroky
- Upraviť main.py na použitie auth_service pre hashovanie.
- Pridať print statements do google_callback.
- Požiadať používateľa o kontrolu .env.
