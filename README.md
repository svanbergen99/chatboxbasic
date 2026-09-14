# ChatBox Basic

Een zo simpel mogelijke lokale chatbox. Geen account, geen login, geen cookies voor authenticatie en geen externe dependencies.

## Starten

1. Zorg dat Aero lokaal draait op poort `8091` en Diva op `8090` als je Diva wilt gebruiken.
2. Open CMD in deze map.
3. Start:

```bat
python server.py
```

4. Open:

```text
http://localhost:8080
```

Normale berichten gaan naar Aero. Berichten die beginnen met `Diva:` of `Diva ` gaan naar Diva.

De zichtbare chatgeschiedenis wordt alleen lokaal in de browser opgeslagen via `localStorage`.
