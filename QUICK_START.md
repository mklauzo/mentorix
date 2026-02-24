# Mentorix AI Agent – Quick Start

Mentorix to platforma SaaS do tworzenia chatbotów RAG (Retrieval-Augmented Generation). Każdy **profil** (tenant) to niezależny chatbot z własną bazą dokumentów, modelem LLM, brandingiem i unikalnym linkiem. Chatboty można osadzać jako iframe na dowolnej stronie.

---

## Wymagania

- Docker + Docker Compose v2
- Domena z DNS wskazującym na serwer (dla TLS)
- **Klucz API OpenAI** (do embeddings dokumentów): https://platform.openai.com/api-keys
  - Wymagany nawet przy używaniu Ollama, bo embeddingi (indeksowanie dokumentów) korzystają z `text-embedding-3-small`
  - Koszt embeddings jest pomijalny (~$0 przy typowym użyciu)
  - *Można pominąć tylko jeśli nie używasz dokumentów RAG*

> **Chcesz w pełni bezpłatne LLM?** Ollama uruchamia się automatycznie razem ze stosem Docker. Wystarczy wybrać model `ollama:*` w ustawieniach profilu. Klucz OpenAI potrzebny jest tylko do indeksowania dokumentów.

---

## 1. Pierwsze uruchomienie

```bash
# Sklonuj repo i wejdź do katalogu
cd mentorix

# Skopiuj .env i wygeneruj losowe hasła/klucze
./scripts/generate_secrets.sh
```

Skrypt tworzy plik `.env` z losowo wygenerowanymi wartościami dla:
`SECRET_KEY`, `JWT_SECRET_KEY`, `IP_HASH_SALT`, `POSTGRES_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`

---

## 2. Konfiguracja `.env`

Otwórz `.env` i uzupełnij **ręcznie** poniższe wartości (reszta jest już wygenerowana):

```env
# Twoja domena (Traefik pobierze certyfikat TLS od Let's Encrypt)
DOMAIN=twojadomena.pl
ACME_EMAIL=admin@twojadomena.pl

# Klucz API OpenAI – WYMAGANY
OPENAI_API_KEY=sk-...

# Dozwolone originy dla panelu admina
ADMIN_CORS_ORIGINS=https://twojadomena.pl
```

### Dashboard Traefik (opcjonalne)

Jeśli chcesz dostęp do panelu Traefik, wygeneruj hash hasła:
```bash
htpasswd -nb admin 'TwojeHaslo'
```
Wynik (np. `admin:$apr1$...`) wklej do `.env` jako `TRAEFIK_DASHBOARD_PASSWORD_HASH`.

> **Ważne:** Każdy znak `$` w hashu musisz zamienić na `$$` (wymaganie Docker Compose).
> Przykład: `admin:$$apr1$$xxxx$$yyyy`

---

## 3. Certyfikat TLS (Let's Encrypt)

Traefik pobiera certyfikat automatycznie przy pierwszym uruchomieniu.

**Wymagania:**
- DNS domeny musi wskazywać na IP serwera (`A record`)
- Port **80** musi być dostępny z internetu (HTTP challenge)
- `DOMAIN` i `ACME_EMAIL` ustawione w `.env`

**Przygotowanie pliku na certyfikaty** (jednorazowo):
```bash
touch traefik/acme.json
chmod 600 traefik/acme.json
```

Certyfikat jest pobierany automatycznie w ciągu ~30 sekund od pierwszego żądania HTTPS.

**Sprawdź status certyfikatu:**
```bash
docker compose logs traefik 2>&1 | grep -i "acme\|certif\|obtain"
```

**Certyfikat się nie pojawia?** Najczęstsze przyczyny:
- DNS jeszcze się nie propagował (poczekaj do 24h lub sprawdź: `dig +short twojadomena.pl`)
- Port 80 jest zablokowany przez firewall: `sudo ufw allow 80`
- Plik `acme.json` ma złe uprawnienia: `chmod 600 traefik/acme.json`

---

## 4. Uruchomienie

```bash
# Uruchom wszystkie kontenery
docker compose up -d

# Uruchom migracje bazy danych
docker compose exec backend alembic upgrade head
```

Aplikacja dostępna pod:
- **Frontend / Panel admina**: `https://twojadomena.pl/admin`
- **API**: `https://twojadomena.pl/api/v1`
- **Swagger (dev)**: `https://twojadomena.pl/api/docs` *(tylko gdy ENVIRONMENT=development)*

---

## 4. Tworzenie pierwszego konta (superadmin)

Po uruchomieniu wykonaj jednorazowe żądanie HTTP tworzące konto superadmina:

```bash
curl -X POST https://twojadomena.pl/api/v1/auth/register-superadmin \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@twojadomena.pl", "password": "TwojeHasloSuperadmina"}'
```

> **Ważne:** Endpoint działa tylko raz – jeśli superadmin już istnieje, zwraca 403. Nie trzeba go wyłączać ręcznie.

Zaloguj się na `https://twojadomena.pl/admin/login` używając powyższych danych.

---

## 5. Pierwsze kroki w panelu

### Jako superadmin:

1. **Utwórz profil chatbota** → *Wszystkie profile → Nowy profil*
   - Podaj nazwę, slug (część URL), kolor, model LLM, dzienny limit tokenów
   - System prompt definiuje zachowanie i wiedzę chatbota

2. **Utwórz admina dla profilu** → *Użytkownicy → Dodaj użytkownika*
   - Wybierz rolę `admin` i przypisz profil (`tenant_id`)
   - Admin samodzielnie zarządza dokumentami i rozmowami swojego profilu

3. **Wgraj dokumenty** → *Dokumenty* (lub przez konto admina)
   - Obsługiwane formaty: PDF, DOCX, TXT, MD, HTML (max 25 MB)
   - Przetwarzanie odbywa się w tle (Celery) – status: Oczekuje → Przetwarza → Gotowy

4. **Skopiuj link do chatbota** → *Wszystkie profile → ikona kopiowania*
   - URL: `https://twojadomena.pl/chat/{tenant_id}`
   - Gotowy kod iframe dostępny w panelu *Mój profil*

---

## 6. Hasła i gdzie są przechowywane

| Sekret | Plik | Opis |
|--------|------|------|
| `SECRET_KEY` | `.env` | Klucz aplikacji FastAPI |
| `JWT_SECRET_KEY` | `.env` | Podpisywanie tokenów JWT (sesje admina) |
| `IP_HASH_SALT` | `.env` | Sól do haszowania adresów IP użytkowników |
| `POSTGRES_PASSWORD` | `.env` | Hasło do bazy PostgreSQL |
| `OPENAI_API_KEY` | `.env` | Klucz API OpenAI – **wpisz ręcznie** |
| `GRAFANA_ADMIN_PASSWORD` | `.env` | Hasło do Grafana (jeśli używasz monitoringu) |
| Hasło superadmina | Baza danych | Ustawiasz przez `/auth/register-superadmin` |

> Plik `.env` jest w `.gitignore` – nigdy go nie commituj.

---

## 7. Zarządzanie użytkownikami

| Rola | Może |
|------|------|
| `superadmin` | Tworzy/usuwa profile i wszystkich użytkowników |
| `admin` | Zarządza własnym profilem, dokumentami, tworzy/usuwa konta `user` w swoim profilu |
| `user` | Podgląd rozmów i dokumentów własnego profilu (read-only) |

Panel admina: `https://twojadomena.pl/admin`

---

## 8. Ollama – lokalne, bezpłatne modele LLM

Ollama uruchamia się automatycznie razem z pozostałymi kontenerami (`docker compose up -d`).
Przy pierwszym starcie **nie ma żadnych modeli** – trzeba je pobrać ręcznie.

### Pobieranie modeli

```bash
# Lekki, szybki (dobry start)
docker compose exec ollama ollama pull llama3.2

# Większy, lepsze odpowiedzi
docker compose exec ollama ollama pull llama3.1

# Inne popularne modele
docker compose exec ollama ollama pull mistral
docker compose exec ollama ollama pull gemma3
docker compose exec ollama ollama pull phi4-mini

# Lista pobranych modeli
docker compose exec ollama ollama list
```

### Przypisanie modelu do profilu

W panelu admina: **Edytuj profil → Model LLM → sekcja "Ollama"**.
Wybierz np. `llama3.2 (3B)` i zapisz. Od tej chwili ten chatbot używa lokalnego modelu.

### Wymagania sprzętowe (CPU)

| Model | RAM (CPU) | Czas odpowiedzi |
|-------|-----------|-----------------|
| llama3.2 (3B) | ~4 GB | ~10–30 s |
| mistral (7B) | ~8 GB | ~20–60 s |
| llama3.1 (8B) | ~10 GB | ~30–90 s |

> Serwer z GPU: odkomentuj sekcję `deploy` w `docker-compose.yml` dla usługi `ollama`.
> Czas odpowiedzi na GPU jest 10–30× krótszy.

### Logi Ollama

```bash
docker compose logs -f ollama
```

---

## 9. Auto-start po restarcie serwera

Wszystkie kontenery (w tym Ollama) mają ustawione `restart: unless-stopped` – startują automatycznie po restarcie serwera, o ile Docker sam startuje przy rozruchu systemu.

**Upewnij się, że Docker startuje przy rozruchu:**

```bash
# Jednorazowo na serwerze:
sudo systemctl enable docker
```

Sprawdź:
```bash
sudo systemctl is-enabled docker   # powinno zwrócić "enabled"
```

---

## 10. Monitoring (opcjonalne)

```bash
make up-monitoring   # Uruchamia Prometheus + Grafana
```

- **Grafana**: `https://twojadomena.pl/grafana`
  - Login: `admin` / wartość `GRAFANA_ADMIN_PASSWORD` z `.env`
- **Metryki Prometheus**: `https://twojadomena.pl/metrics` *(zabezpieczone przez Traefik)*

---

## 11. Przydatne komendy

```bash
make logs-backend     # Logi backendu
make logs-worker      # Logi workera (przetwarzanie dokumentów)
make shell-backend    # Bash wewnątrz kontenera backendu
make shell-db         # psql – bezpośredni dostęp do bazy
make backup           # Ręczny backup PostgreSQL
make down             # Zatrzymaj wszystko
make down-v           # Zatrzymaj i usuń dane (DESTRUKTYWNE)

# Ollama
docker compose exec ollama ollama list     # Lista modeli
docker compose exec ollama ollama pull llama3.2  # Pobierz model
docker compose logs -f ollama              # Logi Ollama
```

---

## 12. Struktura URL

```
/                          → Przekierowanie do /admin
/admin                     → Panel administracyjny
/admin/login               → Logowanie
/admin/profiles            → Wszystkie profile (superadmin)
/admin/my-profile          → Mój profil (admin/user)
/admin/users               → Zarządzanie użytkownikami
/admin/documents           → Dokumenty (z ?tenant_id=...)
/admin/conversations       → Historia rozmów
/chat/{tenant_id}          → Publiczny chatbot (embeddable iframe)
/api/v1/...                → REST API
/api/docs                  → Swagger UI (tylko development)
```
