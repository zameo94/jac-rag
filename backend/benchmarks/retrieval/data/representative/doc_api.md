# Riferimento API Nordwind Cloud

## Autenticazione

Tutte le richieste devono includere l'intestazione X-Api-Key con una chiave valida. Le chiavi si ottengono dall'endpoint /v2/token, che restituisce un token valido per sessanta minuti.

## Endpoint dispositivi

| Metodo | Percorso | Descrizione |
| --- | --- | --- |
| GET | /v2/devices | Elenco dei dispositivi |
| POST | /v2/devices | Registrazione di un dispositivo |
| DELETE | /v2/devices/{id} | Rimozione di un dispositivo |

## Endpoint misure

Le misure si leggono con GET /v2/measurements. E possibile filtrare per intervallo temporale usando i parametri from e to in formato ISO 8601.

## Codici di errore

| Codice | Significato | Azione consigliata |
| --- | --- | --- |
| E-4001 | Chiave non valida | Verificare X-Api-Key |
| E-4021 | Dispositivo non autorizzato | Rigenerare le credenziali |
| E-4290 | Limite di richieste superato | Attendere e riprovare |

## Limiti di utilizzo

Il piano standard consente 1000 richieste al minuto per chiave. Superata questa soglia il servizio risponde con stato 429. Per volumi superiori e necessario richiedere un piano dedicato.
