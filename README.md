# 💰 FinBot — Personal Finance Intelligence via WhatsApp

A personal finance tracker that lives entirely inside WhatsApp.  
No new app to install. No new habit to build.  
Tracks UPI payments, bill photos, and cash expenses — built specifically for how Indians actually spend money.

---

## How It Works

Send a WhatsApp message → FinBot parses it → logs it → learns your habits over time.

| You send | FinBot does |
|---|---|
| Forward a GPay/PhonePe screenshot | Extracts merchant, amount, date — logs automatically |
| Photo of a bill or receipt | OCR extracts every line item |
| PDF bank statement | Bulk imports all transactions |
| `"40 pav bhaji"` | Logs ₹40 under Food instantly |
| `"report"` | Sends you a dashboard link |

---

## Core Feature — Smart Merchant Caching

The bot remembers merchants the way humans do — frequent places get remembered forever, one-time visits are forgotten.

| Appearances | Memory Duration |
|---|---|
| 1st time | Ask once, cache for 7 days |
| 3+ times in 7 days | Extend to 30 days |
| 10+ times in 30 days | Extend to 90 days |
| 20+ times in 90 days | Promoted to permanent DB — never asked again |

Built on Redis with TTL-based keys and frequency counters.

---

## Tech Stack

| Layer | Technology |
|---|---|
| WhatsApp Bot | Twilio WhatsApp API |
| Backend | FastAPI + Uvicorn |
| Task Queue | Celery + Redis |
| Caching | Redis (TTL + frequency logic) |
| Database | MySQL via SQLAlchemy |
| OCR | EasyOCR + OpenCV |
| PDF Parsing | PyMuPDF |
| NLP | spaCy + Regex |
| ML Categorization | Scikit-learn |
| Dashboard | HTML + JS + Plotly |
| File Storage | Cloudinary |
| Deployment | Render |

---

## Project Structure

```
finbot/
├── app/
│   ├── main.py                  # FastAPI entry point, Twilio webhook
│   ├── config.py                # Env vars and settings
│   ├── bot/                     # WhatsApp message handler and responder
│   ├── parsers/                 # UPI, bill, PDF, text parsers
│   ├── ocr/                     # OpenCV preprocessing + EasyOCR
│   ├── cache/                   # Redis TTL cache + merchant promoter
│   ├── ml/                      # Categorization model
│   ├── intelligence/            # Habit detection, anomaly alerts, reports
│   ├── tasks/                   # Celery async tasks
│   ├── db/                      # SQLAlchemy models and CRUD
│   ├── dashboard/               # Dashboard routes and Plotly charts
│   └── utils/                   # Helpers — phone, date, image upload
├── frontend/                    # Dashboard HTML/CSS/JS
├── tests/                       # Pytest test suite
├── sample_data/                 # Sample screenshots, bills, PDFs for testing
├── scripts/                     # DB seed, ML training scripts
├── .env.example                 # Env var template
├── docker-compose.yml           # FastAPI + Redis + MySQL + Celery
└── requirements.txt
```

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/PriyanshuM04/FINBOT.git
cd FINBOT
python -m venv .venv
source .venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Download spaCy model

```bash
python -m spacy download en_core_web_sm
```

### 3. Configure environment

```bash
cp .env.example .env
# Fill in all values — see .env.example for required keys
```

### 4. Start services with Docker

```bash
docker-compose up -d
```

This starts MySQL, Redis, and the Celery worker together.

### 5. Run the FastAPI server

```bash
uvicorn app.main:app --reload
```

### 6. Expose locally for Twilio (dev only)

```bash
ngrok http 8000
# Copy the https URL → paste into Twilio WhatsApp sandbox webhook
```

---

## Environment Variables

Create a `.env` file based on `.env.example`:

```
# Twilio
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# MySQL
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/finbot

# Redis
REDIS_URL=redis://localhost:6379/0

# Cloudinary
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=

# App
SECRET_KEY=your-secret-key-here
ENVIRONMENT=development
```

---

## Build Phases

| Phase | What gets built | Timeline |
|---|---|---|
| 1 | Core bot — text input, MySQL, Twilio webhook | Week 1–2 |
| 2 | UPI screenshot parser (GPay, PhonePe, Paytm) | Week 3–4 |
| 3 | Redis caching + merchant categorization | Week 5 |
| 4 | Habit detection + anomaly alerts | Week 6 |
| 5 | Web dashboard with Plotly | Week 7–8 |
| 6 | PDF bank statement import | Week 9 |
| 7 | Polish, deploy to Render, demo video | Week 10 |

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Why This Project

- Solves a real Indian-context problem — UPI-dominant, cash-heavy, receipt-less spending culture  
- Lives inside WhatsApp — zero app adoption barrier  
- UPI screenshot parsing across multiple formats is a genuinely hard engineering problem  
- Redis TTL caching with frequency-based promotion is real system design — strong interview topic  
- Full pipeline: CV → NLP → caching → backend → database → frontend → deployment → bot  
- Live demo in an interview: send a WhatsApp message and show the response in real time

---

## License

MIT
