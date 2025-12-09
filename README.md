# Mark Six History & Prediction

## Features
- Scrape and store full Mark Six history in `data/mark_six.sqlite`
- Web app to browse history, search, page jump, and incremental updates
- Predict tools: duplicate check, non-duplicate generator, smart suggestion
- Insights: patterns that never occur and rarity stats

## Setup
- Create a virtual environment
  - `python -m venv .venv`
  - `./.venv/Scripts/activate`
- Install dependencies
  - `pip install -r requirements.txt`

## Build Database
- Full scrape: `python scrape_mark_six.py`
- Incremental update from web UI: open History → Update Records

## Run Web
- `python web/app.py`
- Open `http://127.0.0.1:8000/`

## Pages
- Home: instructions and navigation
- History: search, pagination, update button
- Predict: duplicate check, generator, smart suggest (trend window)
- Insights: never-occurring patterns and rarity metrics

## GitHub Push
- Initialize local repo (already done below)
- Create a GitHub repository (e.g., `mark-six-history`)
- Connect and push:
  - `git remote add origin https://github.com/<YOUR_USERNAME>/<REPO_NAME>.git`
  - `git push -u origin main`

