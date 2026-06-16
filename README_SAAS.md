# 🏪 Stationary Shop AI System - Multi-Tenant SaaS

**OKCredit Finternship Project - Multi-Tenant SaaS Version**

A complete multi-tenant SaaS solution for stationary shops featuring AI-powered OCR, real-time inventory management, and ML-based sales forecasting.

## 🌟 Features

### 🔐 Multi-Tenant Authentication
- Secure email/password signup and login via Supabase Auth
- Row-Level Security (RLS) ensures complete data isolation
- Each user gets their own private inventory and sales data

### 📸 Gemini 2.5 Flash OCR
- Extract items from bill images automatically
- Handles both printed and handwritten text
- Supports text input as well
- Smart item matching with fuzzy logic

### 📦 Inventory Management
- Real-time stock tracking
- Manual sale recording
- Stock addition
- Add new items on-the-fly
- Risk-based alerts (🔴 Critical, 🟠 High, 🟡 Medium, 🟢 Safe)

### 📈 ML-Powered Predictions
- Random Forest regression for sales forecasting
- 30-day stockout predictions
- Visual analytics dashboard
- Item-specific trend analysis
- Seasonal pattern detection (weekend vs weekday)

### 🎨 Beautiful UI
- Dark theme with gradient design
- Responsive Gradio interface
- 3-page navigation flow:
  1. **Auth Page**: Login/Signup
  2. **Onboarding**: First-time setup with guided instructions
  3. **Dashboard**: Full featured app with tabs

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Gradio Frontend                      │
│  (Auth → Onboarding → Dashboard with 3 tabs)           │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│                   app.py (Python)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ ShopDataStore│  │  GeminiOCR   │  │ PredictionEng││ │
│  │  (Supabase)  │  │ (Gemini 2.5) │  │(RandomForest)││ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└────────────────┬──────────────┬────────────────────────┘
                 │              │
        ┌────────▼──────┐  ┌────▼─────────┐
        │   Supabase    │  │  Google AI   │
        │  PostgreSQL   │  │   (Gemini)   │
        │   + Auth      │  │              │
        └───────────────┘  └──────────────┘
```

## 📊 Database Schema

### `inventory` table
```sql
- id (UUID, primary key)
- user_id (UUID, foreign key to auth.users)
- item_name (TEXT)
- stock (INTEGER)
- avg_daily_sale (FLOAT)
- reorder (INTEGER)
- price (FLOAT)
```

### `sales_history` table
```sql
- id (UUID, primary key)
- user_id (UUID, foreign key to auth.users)
- date (DATE)
- item_name (TEXT)
- units_sold (INTEGER)
- day_of_week (INTEGER)
- month (INTEGER)
- is_weekend (INTEGER)
```

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Supabase account
- Gemini API key

### 1. Clone & Install

```bash
cd kirana
pip install -r requirements.txt
```

### 2. Setup Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your keys:
GEMINI_API_KEY=your-gemini-api-key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
```

### 3. Setup Supabase Database

1. Create a Supabase project at https://supabase.com
2. Run the SQL from `.env.example` in SQL Editor
3. Enable Email authentication in Auth settings

### 4. Run Locally

```bash
python app.py
```

Open http://localhost:8080

## 🌐 Deploy to Google Cloud Run

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete deployment instructions.

**Quick command:**

```bash
gcloud run deploy stationary-shop-ai \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=xxx,SUPABASE_URL=xxx,SUPABASE_KEY=xxx
```

## 📁 Project Structure

```
kirana/
├── app.py                 # Main application (multi-tenant SaaS)
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── .env.example          # Environment template + SQL setup
├── DEPLOYMENT.md         # Google Cloud Run guide
├── README.md             # Original project readme
└── README_SAAS.md        # This file (SaaS version)
```

## 🔒 Security Features

- ✅ Supabase Row-Level Security (RLS) for data isolation
- ✅ Secure password hashing via Supabase Auth
- ✅ Environment variables for secrets (never committed)
- ✅ User-specific data queries (all filtered by user_id)

## 🎯 Use Case Flow

### New User Journey
1. **Sign up** with email/password
2. **Onboarding**: Add initial inventory items with guided instructions
3. **Dashboard Access**: 
   - Scan bills via OCR
   - Track sales and stock
   - Get AI predictions

### Existing User Journey
1. **Login** with credentials
2. **Direct to Dashboard** (skip onboarding if inventory exists)
3. **Daily Operations**:
   - Upload bill images → Auto-extract items → Confirm
   - View real-time inventory with risk indicators
   - Generate 30-day forecasts
   - Analyze item trends

## 🤖 Tech Stack

- **Frontend**: Gradio (Python-based UI framework)
- **Backend**: Python 3.10
- **Database**: Supabase (PostgreSQL + Auth)
- **AI/ML**: 
  - Google Gemini 2.5 Flash (OCR)
  - Scikit-learn Random Forest (Predictions)
- **Visualization**: Matplotlib
- **Deployment**: Google Cloud Run + Docker

## 📝 API Keys Setup

### Gemini API Key
1. Go to https://makersuite.google.com/app/apikey
2. Create/Sign in to Google account
3. Click "Create API Key"
4. Copy and add to `.env`

### Supabase Keys
1. Create project at https://supabase.com
2. Go to Settings → API
3. Copy `Project URL` and `anon public` key
4. Add to `.env`

## 🐛 Troubleshooting

**OCR not working?**
- Check Gemini API key is valid
- Verify image format (JPG, PNG supported)

**Database errors?**
- Ensure SQL schema is created in Supabase
- Check RLS policies are enabled
- Verify user is logged in (user_session not None)

**Login fails?**
- Enable Email auth in Supabase dashboard
- Check SUPABASE_URL and KEY are correct

## 📄 License

Built for OKCredit Finternship Project

## 👨‍💻 Developer

[Your Name]

---

**Powered by Gemini 2.5 Flash + Supabase + Random Forest ML**

**Content rephrased for compliance with licensing restrictions**
