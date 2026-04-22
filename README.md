# Alliance Selector: VEX Robotics Scouting Ecosystem

This repository contains a suite of advanced scouting and analysis tools designed for the VEX Robotics Competition (V5RC 2025-2026 "Push Back" season). 

---

## 🚀 The Ecosystem

The Alliance Selector project is comprised of four specialized programs that work together to provide a complete scouting solution.

### 1. VEX Scout v11 (The "Eye Test" Edition)
**The Core Analysis Engine.**
A machine learning-powered dashboard that ranks teams based on actual performance rather than tournament rankings.
- **Key Features**: TrueSkill ratings, OPR calculation, Sleeper/Fraud detection, and "Eye Test" manual overrides.

### 2. Match Predictor
**Live Outcome Forecasting.**
Uses TrueSkill and historical performance data to predict the outcome of upcoming matches in real-time.
- **How it Works**: It fetches live match schedules and calculates win probabilities. It uses a "Chaos Factor" (beta) to ensure predictions remain realistic and accounts for the volatility of VEX matches.
- **Power Ratings**: Teams are assigned a normalized Power Rating (0-100) based on their percentile rank within the event, making it easy to identify top-tier threats.

### 3. Spirit Scout Tracker
**Real-Time Division Scouting.**
A specialized tool for the Spirit division at VEX Worlds to track upcoming matches involving future partners or opponents.
- **The Watchlist**: Automatically identifies every match featuring a team you will play with or against later in the day.
- **Persistent Notes**: Includes a glassmorphism-style note-taking modal. Observations are saved to `team_notes.json` and persist even after the server restarts, with visual indicators (📝) appearing on the match list once a team has been scouted.

### 4. Design Award Checker
**Award Eligibility Utility.**
Verifies if teams are eligible for the Design Award at the World Championship by checking their award history.
- **Logic**: It cross-references the current division roster against RobotEvents data to identify teams that have won a Design Award at a world-qualifying event (Signature Events, Regional Championships, etc.).

---

## 🧠 Core Metrics and Algorithms

### A. TrueSkill Rating System (Used in Scout & Predictor)
A Bayesian rating system (originally for Xbox Live) that estimates a team's skill (`mu`) and uncertainty (`sigma`). 
- **Conservative Estimate**: We use `mu - 3*sigma` for rankings to ensure we don't overrate teams that have only played a few matches.
- **Chaos Factor**: The Match Predictor incorporates a "beta" variable to account for the inherent randomness of V5RC gameplay.

### B. OPR (Offensive Power Rating)
Uses Linear Algebra (Least Squares) to solve a system of equations based on alliance scores, estimating each robot's individual point contribution. This is the primary metric for identifying **Sleepers** who contribute heavily to their alliance but may have a losing record.

### C. Sleeper & Fraud Detection
- **Sleepers**: Highly capable teams (High OPR, high skills, elite auto) that are currently ranked low due to schedule luck.
- **Frauds**: Top-ranked teams that show "red flags" like weak schedules, low clutch rates in close games, or losing to much lower-seeded opponents.

### D. Machine Learning (Scout Brain)
A **Random Forest Classifier** trained on thousands of matches from the current season. It predicts the probability of a team winning the tournament based on 10 performance variables, including qualification and elimination win rates.

---

## 🛠️ Installation and Running

### Standalone Build
1. Run `build.bat`.
2. The standalone executable will be generated in the `dist/` folder.

### Development Mode
1. Install dependencies: `pip install flask flask-cors pandas numpy scikit-learn joblib requests`.
2. Run the tools:
   - **Main App**: `python launcher.py`
   - **Scout Tracker**: `python scout_tracker/scout_tracker.py`
   - **Match Predictor**: `python match_predictor/predictor.py`

---

## 📊 Data Persistence
- `team_notes.json`: Scouting observations and autonomous patterns.
- `manual_ratings.json`: "Eye Test" scores (1-10) that override AI rankings.
- `event_cache.json`: Optimized RobotEvents API caching to prevent rate-limiting.
- `scout_brain_v11.pkl`: The serialized machine learning model.
