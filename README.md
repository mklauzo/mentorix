# Mentorix

Platforma do tworzenia i zarządzania chatbotami opartymi na własnej bazie wiedzy (RAG). Każdy chatbot działa jako niezależny profil z własnymi dokumentami, modelem AI i ustawieniami.

## Do czego służy?

Mentorix pozwala firmom i organizacjom uruchomić inteligentnego asystenta, który odpowiada **wyłącznie na podstawie dostarczonych dokumentów** — bez halucynacji z internetu. Chatbot można osadzić na stronie www jako widget (iframe).

Przykłady zastosowań: obsługa klienta, baza wiedzy produktowej, wewnętrzny asystent firmy, FAQ dla klientów.

## Możliwości

- **Własna baza wiedzy** — wgraj dokumenty PDF, DOCX, TXT, MD; system automatycznie je przetwarza i indeksuje
- **Wiele profili** — każdy tenant to osobny chatbot z własnym modelem, promptem i brandingiem
- **Wybór modelu AI** — OpenAI (GPT-4o), Anthropic (Claude), Google (Gemini) lub lokalny Ollama (llama3, mistral i inne)
- **Lokalne embeddingi** — domyślnie `nomic-embed-text` przez Ollama, bez wysyłania danych do zewnętrznych API
- **Panel administracyjny** — zarządzanie dokumentami, użytkownikami, historią rozmów i limitami tokenów
- **Role użytkowników** — superadmin, admin (zarządza swoim profilem), user (podgląd)
- **Limity użycia** — dzienny i miesięczny limit tokenów na profil
- **Bezpieczeństwo** — ochrona przed prompt injection, blokada brute-force, brak przechowywania IP

## Wymagania

- Docker + Docker Compose
- VPS z min. 4 GB RAM (8 GB przy lokalnych modelach Ollama)

## Szybki start

```bash
cp .env.example .env
./scripts/generate_secrets.sh
touch traefik/acme.json && chmod 600 traefik/acme.json
docker compose up -d
docker compose exec backend alembic upgrade head
```

Następnie utwórz konto superadmina przez `POST /api/v1/auth/register-superadmin` i zaloguj się pod adresem `/admin`.

## Technologie

Backend: FastAPI · PostgreSQL + pgvector · Celery + Redis
Frontend: Next.js 14 · TypeScript · Tailwind CSS
Proxy: Traefik v3 z automatycznym TLS (Let's Encrypt)
