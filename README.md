# API Williams Barbearia → N8N / WhatsApp

API que lê o sistema BestBarbers (`agendamentos.bestbarbers.app/barbershop/williamsbarbearia`)
e expõe horários **livres + ocupados** dos 3 barbeiros + aba **Sem preferência**.

## Rodar local

```powershell
cd C:\Users\alves\api-williams
python -m venv .venv; .\.venv\Scripts\Activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Teste: http://localhost:8000/docs

## Easypanel

1. Suba a pasta para um repo Git.
2. Easypanel → New Service → From Git → selecione o repo.
3. Porta `8000`, env conforme `.env.example` (`API_KEY` recomendado).
4. Healthcheck path `/health`.

## Endpoints

- `GET /health`
- `GET /barbers` → 3 + `{id:"general", name:"Sem preferência"}`
- `GET /services` → id, name, time_required, price
- `GET /availability?date=YYYY-MM-DD&barbeiro=sem_preferencia|william|16464&service_ids=40451,41271&turno=tarde`
- `GET /availability/all?date=...&service_ids=...&turno=...` → 3 + sem preferência
- `GET /availability/range?start=...&days=7&barbeiro=...` → intervalo
- `GET /ai/context?date=...&turno=tarde` → `{"texto": "..."}` pronto p/ LLM

`barbeiro` aceita nome parcial, ID ou `sem_preferencia/general/qualquer`.
`turno`: `manha|tarde|noite`. `service_ids`: soma duração igual ao site (padrão 40451 = Corte 40min).

## N8N (HTTP Request)

```
GET {{$env.API_BASE}}/availability?date={{ $json.data }}&barbeiro={{ $json.barbeiro_ou_general }}&turno={{ $json.turno }}&service_ids=40451
Header X-API-Key: xxx
```

Prompt IA: "Se cliente não citar barbeiro use barbeiro=sem_preferencia. Converta 'amanhã/terça' para YYYY-MM-DD (America/Sao_Paulo, nunca passado). Use `texto_ia` para responder."
