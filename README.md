# KCD Chatbox — development

Deze branch bouwt ChatBox Basic om tot de KCD Chatbox-gateway. GitHub is alleen het ontwikkelplatform; de uiteindelijke runtime moet zelfstandig op ProjectAI kunnen draaien.

## Pagina's

- `/beheer` — Aero + Diva
- `/collega/casey` — alleen Casey
- `/collega/dee` — alleen Dee

## Chatroutes

- `/api/chat/1` — Aero
- `/api/chat/2` — Diva
- `/api/chat/3` — Casey
- `/api/chat/4` — Dee

De server controleert bij iedere chatrequest welke chat-ID de huidige sessie mag gebruiken.

## Sessierechten

- `beheer` → chat 1 en 2
- `casey` → alleen chat 3
- `dee` → alleen chat 4

Sessies worden in een `HttpOnly` cookie bijgehouden. In productie moet `KCD_COOKIE_SECURE=1` worden gebruikt.

## Collega-handoff

Het collegaportaal vraagt server-to-server een eenmalige toegang aan via:

```text
POST /api/handoff/issue
X-KCD-Handoff-Secret: <server-secret>
Content-Type: application/json

{"assistant":"casey","message":"optionele eerste vraag"}
```

De server geeft een korte redirect-URL terug zoals:

```text
/collega/casey?code=<eenmalige-code>
```

De code is standaard 60 seconden geldig, wordt bij de eerste succesvolle opening vernietigd en daarna uit de adresbalk verwijderd. Een meegegeven eerste vraag wordt server-side aan de nieuwe sessie gekoppeld en één keer door de chatfrontend opgehaald.

De echte `KCD_HANDOFF_SECRET` hoort alleen in serverconfiguratie en nooit in GitHub of browser-JavaScript.

## Development-sessies

Alleen wanneer `KCD_DEV_MODE=1` staat is deze testendpoint beschikbaar:

```text
POST /api/dev/session
{"role":"casey"}
```

`KCD_DEV_MODE` staat standaard uit.

## Belangrijke environment-variabelen

Zie `.env.example`. `server.py` leest gewone OS-environmentvariabelen; het laadt `.env` niet automatisch.

Casey en Dee blijven offline totdat respectievelijk `CASEY_URL` en `DEE_URL` zijn ingesteld.
