# VEX Scout v11: The Eye Test Edition
**A Comprehensive Guide to the Ultimate Alliance Selection Tool**

---

## 1. Introduction

**VEX Scout** is an advanced, machine learning-powered alliance selection assistant built specifically for the VEX Robotics Competition (V5RC 2025-2026 "Push Back" season). 

Instead of relying solely on the official tournament rankings (which can be heavily skewed by lucky or unlucky schedules), VEX Scout pulls raw match data directly from the RobotEvents API. It applies advanced statistical models (TrueSkill, OPR) and machine learning to find out how good a team *actually* is.

The goal of this program is to help alliance captains build the perfect playoff alliance by identifying:
- **Sleepers**: Highly capable, underrated teams that had bad luck in qualifiers.
- **Frauds**: Overrated teams sitting at the top of the leaderboard who were carried by an easy schedule and will likely choke in eliminations.
- **Synergy**: The perfect partner that covers your robot's specific weaknesses.

### What's New in v11 (The "Eye Test" Edition)
Data isn't everything. A robot might have great stats but bad drivers, or poor stats but amazing build quality. Version 11 introduces the **Eye Test**—allowing human scouts to override the AI based on what they actually see on the field. It also introduces **Elimination Tracking**, valuing playoff performance far more than qualification performance.

---

## 2. Installation and Running

VEX Scout is designed to be accessible to anyone, even those who don't know how to code.

### The Standalone Build (For non-programmers)
You don't need Python installed to share this with your team.
1. Double-click the included `build.bat` script.
2. Wait a few minutes. PyInstaller will package the Python backend and web frontend into a single standalone executable.
3. The result is placed in the `dist\VEX Scout` folder. You can zip this folder and send it to anyone; they just run `VEX Scout.exe`.

### Development Mode (For programmers)
If you want to edit the code and run it live:
1. Ensure Python is installed.
2. Run `pip install flask flask-cors pandas numpy scikit-learn joblib requests`.
3. Run `python launcher.py`. This starts the backend server and automatically opens your web browser to `http://localhost:5000`.

---

## 3. Architecture Overview

The application is split into two distinct parts:

1. **The Backend (`vex_scout_v11.py`)**: A Python Flask web server. This file does 100% of the heavy lifting. It queries the RobotEvents API, crunches the numbers using linear algebra and machine learning, and serves the data.
2. **The Frontend (`index.html`)**: A vanilla HTML/JS/CSS single-page application. It provides a beautiful dashboard that requests the analyzed data from the Python backend.
3. **Data Persistence**: The app saves your work locally using JSON files.
   - `team_notes.json`: Your typed scouting notes.
   - `manual_ratings.json`: Your 1-10 "Eye Test" ratings.
   - `head_to_head.json`: Bracket tracking for who beat who.
   - `event_cache.json`: Caches API data so you don't get rate-limited by RobotEvents.
   - `scout_brain_v11.pkl`: The trained machine learning model.

---

## 4. Core Metrics and Algorithms

How does the program actually figure out who is good? It uses a combination of several advanced metrics.

### A. TrueSkill Rating System
Originally developed by Microsoft for Xbox Live matchmaking, TrueSkill is a Bayesian rating system perfect for team-based games like VEX. 
- Every team starts with a skill estimate (`mu` = 25) and a high uncertainty (`sigma` = 8.33).
- When an alliance wins a match, their `mu` goes up and their `sigma` goes down (we become more certain they are good).
- By using the "conservative" TrueSkill estimate (`mu - 3 * sigma`), the algorithm avoids overrating teams that have only played 1 or 2 lucky matches.

### B. OPR (Offensive Power Rating)
In VEX, your alliance gets a single combined score. How do you know which robot did the work? OPR solves this using **Linear Algebra**.
- It builds a massive matrix of every match played, treating every team as an unknown variable in a system of equations (e.g., `Team A + Team B = 65 points`).
- It uses the "Least Squares" method to solve this matrix, resulting in an estimate of how many points each individual robot contributes to a match on their own.

### C. Sleeper Detection
The algorithm looks for teams outside the Top 10 that possess "hidden gem" qualities. A team earns "Sleeper Points" for:
- **High Ceiling**: Their OPR-based ceiling is >25% higher than their average points.
- **Strong Skills**: A skills score over 160 (proving the robot works perfectly in solo, non-random environments).
- **Elite Auto**: Consistent autonomous performance (>7 points avg).
- **Giant Killers**: They have beaten 3 or more higher-ranked alliances.
- **Clutch Performers**: They win >60% of matches that are decided by fewer than 12 points.
- **Elimination Performers**: They have multiple playoff wins.
*If a team accumulates 40+ points here, they are officially flagged as a Sleeper.*

### D. Fraud Detection
The algorithm looks at Top 12 teams to find "red flags" that indicate they were carried by luck. A team earns "Fraud Penalty Points" for:
- **Head-to-Head Playoff Losses**: If a #2 seed loses to a #15 seed in elims, this triggers a massive penalty.
- **Choking Close Games**: A clutch rate below 35% in tight matches.
- **Early Elim Exits**: A top 5 seed losing in the Round of 16 or Quarterfinals.
- **Weak Schedule**: Their Strength of Schedule (SP) is significantly below the event average.
- **Losing to Lower Seeds**: Losing to teams they mathematically should have beaten.
*If a top-ranked team hits 30+ penalty points (35 for the Top 5), they are flagged as a Fraud and should be avoided in alliance selection.*

### E. Synergy Scoring
Not all good teams make good partners. If your robot has no autonomous routine, you shouldn't pick another robot with no autonomous routine. The Synergy engine evaluates:
- **Combined Auto**: Do you and the partner sum up to a winning auto bonus (>14 pts)?
- **Covering Weaknesses**: Does the partner have a strong auto when you have a weak one?
- **Combined Scoring**: Does your combined average points reach a winning threshold?
- **Reliability**: Does the partner have a low standard deviation (meaning they are consistent)?

---

## 5. The Machine Learning Model (Scout Brain)

VEX Scout uses a **Random Forest Classifier** (`sklearn.ensemble.RandomForestClassifier`) to predict if a team will be successful.

1. **Training Phase**: When you start the app, it silently queries RobotEvents for up to 25 *recent* tournaments from the *current* season.
2. **Feature Extraction**: It looks at 10 variables for every team: Rank, Auto, SP, WP, Average Points, Standard Deviation, Ceiling, Trend, Qualification Win Rate, and Elimination Win Rate.
3. **The Target**: It checks if those teams went on to win the Tournament Champion award.
4. **The Forest**: It builds 200 "decision trees" that look for complex patterns (e.g., "If rank is bad, but skills and trend are high, team is likely to succeed"). 
5. **The Prediction**: Live at your event, the model looks at the teams and outputs a percentage probability of them winning the tournament.

---

## 6. The Final AI Score Calculation

Every team is given an ultimate 0-100 `Overall_Score`. This is a weighted blend of everything the program calculates:

- **20%** - TrueSkill Rating (Proven skill over time)
- **20%** - Skills Score (Solo robot capability)
- **15%** - Elimination Win Rate (Can they win under pressure?)
- **10%** - Machine Learning Prediction (Historical patterns)
- **10%** - OPR (Individual point contribution)
- **10%** - Ceiling (Maximum potential)
- **10%** - Clutch Rate (Performance in close games)
- **5%** - Consistency (Low standard deviation)

### The Eye Test Override
If a scout manually inputs a 1-10 rating for a team (The Eye Test), the algorithm immediately respects human intuition over raw data. The final score is recalculated as:
**60% Human Rating + 40% AI Score.**

---

## 7. How to Use the Program at an Event

1. **Find your SKU**: Go to your event on RobotEvents.com. Look at the URL. Copy the SKU (e.g., `RE-V5RC-25-1234`).
2. **Load the Event**: Open VEX Scout, paste the SKU, and hit Analyze. 
3. **Review the Tiers**: The dashboard will sort teams into Tier A (Elites), Tier B (Solid), Tier C (Average), and explicitly call out the **Sleepers** and **Frauds**.
4. **Scout the Field**: Walk around. Watch matches. If the AI says a team is Tier A but you see their robot falling apart, click on them and give them a **Manual Rating** of 3. They will plummet in the rankings. If you see a #30 ranked team playing amazing defense, give them a Manual Rating of 9.
5. **Track Head-to-Head**: As elimination brackets begin, use the Head-to-Head tracker to input who beats who. The AI will immediately penalize the losers (updating their Fraud status) and boost the winners.
6. **Pick Your Partner**: When it's time for Alliance Selection, use the Synergy tool, trust the AI's Sleeper picks, avoid the Frauds, and build a winning alliance.
