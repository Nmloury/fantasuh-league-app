# Fantasuh League App

A comprehensive fantasy football analytics platform that transforms raw league data into actionable insights, automated weekly recaps, and performance analysis for the 2025 Fantasuh football league.

## What It Does

**Fantasuh League App** Creates deeper understanding of the current status of the league. Whether you're analyzing draft picks, optimizing lineups, or tracking FAAB investments, this platform provides the analytical insight every fantasy league needs.

### Key Features

- **🤖 AI-Powered Weekly Recaps**: Automated league stories and analysis using OpenAI, delivering engaging narratives about your league's weekly drama
- **📊 Advanced Analytics Dashboard**: 
  - **Lineup Efficiency**: Optimal lineup recommendations using linear programming
  - **FAAB ROI**: Free Agent Acquisition Budget return on investment analysis
  - **Draft ROI**: Comprehensive draft pick value analysis and hindsight evaluation
  - **Luck Index & Expected Wins**: Performance vs. luck analysis to separate skill from fortune
- **🔄 Real-time Data Integration**: Seamless connection to Yahoo Fantasy API for live league data
- **🎨 Interactive Web Interface**: Clean, modern Streamlit-based dashboard with intuitive navigation
- **⚙️ Automated Data Pipeline**: ETL scripts for continuous data processing and metric computation

## 🛠️ Tech Stack

- **Frontend**: Streamlit web application with multi-page analytics dashboard
- **Backend**: Python-based analytics engine with modular library architecture
- **Database**: Supabase (PostgreSQL) with comprehensive fantasy data schema
- **Data Sources**: Yahoo Fantasy API integration with OAuth authentication
- **AI Integration**: OpenAI API for generating weekly recaps and insights
- **Automation**: GitHub Actions for scheduled data updates and recap generation
- **Analytics**: Pandas/NumPy for data analysis, PuLP for optimization algorithms

## Quick Start

### Prerequisites
- Python 3.12+
- Yahoo Fantasy API access
- OpenAI API key
- Supabase account

### Setup

1. **Clone and Install**
   ```bash
   git clone <repository-url>
   cd fantasuh-league-app
   pip install -r requirements.txt
   ```

2. **Environment Configuration**
   Create a `.env` file with:
   ```env
   SUPABASE_URL=your_supabase_url
   SUPABASE_SERVICE_ROLE_KEY=your_supabase_key
   OPENAI_API_KEY=your_openai_key
   YAHOO_CLIENT_ID=your_yahoo_client_id
   YAHOO_CLIENT_SECRET=your_yahoo_client_secret
   ```

3. **Database Setup**
   ```bash
   # Run the SQL schema files in order
   psql -f sql/00_schema.sql
   psql -f sql/10_indices.sql
   psql -f sql/20_views.sql
   ```

4. **Yahoo OAuth Setup**
   ```bash
   python scripts/yahoo_oauth_setup.py
   ```

5. **Launch the App**
   ```bash
   streamlit run app/Home.py
   ```

## Project Structure

```
├── app/                    # Main Streamlit application
│   ├── Home.py            # Dashboard homepage
│   ├── pages/             # Analytics pages
│   │   ├── 1_Weekly_Recap.py
│   │   ├── 2_Lineup_Efficiency.py
│   │   ├── 3_FAAB_ROI.py
│   │   ├── 4_Draft_ROI.py
│   │   └── 5_Luck_and_Expected_Wins.py
│   └── lib/               # Core analytics modules
│       ├── draft_roi.py
│       ├── faab_roi.py
│       ├── lineup_efficiency.py
│       └── expected_wins.py
├── etl/                   # Data pipeline scripts
├── sql/                   # Database schema and views
└── scripts/               # Utility scripts
```

## Key Dependencies

- **streamlit** - Web interface framework
- **supabase** - Database and real-time features
- **yahoo-fantasy-api** - League data integration
- **openai** - AI content generation
- **pandas/numpy** - Data analysis and manipulation
- **pulp** - Linear programming for lineup optimization
- **scipy** - Statistical analysis
