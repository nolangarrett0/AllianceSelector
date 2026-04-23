import math

class TrueSkillRating:
    def __init__(self, mu=25.0, sigma=8.333):
        self.mu = mu
        self.sigma = sigma

def weighted_update_trueskill(winner_ratings, loser_ratings, margin=0, weight=1.8, teammate_protect=True):
    beta = 4.1667
    MAX_MU_CHANGE = 10
    winner_mu = sum(r.mu for r in winner_ratings) / len(winner_ratings)
    winner_sigma = sum(r.sigma**2 for r in winner_ratings)**0.5 / len(winner_ratings)
    loser_mu = sum(r.mu for r in loser_ratings) / len(loser_ratings)
    loser_sigma = sum(r.sigma**2 for r in loser_ratings)**0.5 / len(loser_ratings)
    c = (2 * beta**2 + winner_sigma**2 + loser_sigma**2)**0.5
    t = (winner_mu - loser_mu) / c
    v = math.exp(-t**2 / 2) / (0.5 * (1 + math.erf(t / 2**0.5)) * (2 * math.pi)**0.5 + 0.001)
    w = v * (v + t)
    margin_factor = 1 + min(margin / 50, 0.5)
    for r in winner_ratings:
        delta = (r.sigma**2 / c) * v * margin_factor * weight
        r.mu += min(delta, MAX_MU_CHANGE)
        r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)
    if teammate_protect and len(loser_ratings) == 2:
        for i, r in enumerate(loser_ratings):
            partner = loser_ratings[1 - i]
            partner_ratio = min(partner.mu / r.mu, 1.0) if r.mu > 1 else 1.0
            loss_factor = 0.4 + 0.6 * partner_ratio
            delta = (r.sigma**2 / c) * v * margin_factor * weight * loss_factor
            r.mu -= min(delta, MAX_MU_CHANGE)
            r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)

def simulate():
    target = TrueSkillRating(25.0, 8.333)
    # Assume teammates and opponents are also around 25.0
    
    # 5 wins
    for i in range(5):
        teammate = TrueSkillRating(25.0, 8.333)
        opp1 = TrueSkillRating(25.0, 8.333)
        opp2 = TrueSkillRating(25.0, 8.333)
        weighted_update_trueskill([target, teammate], [opp1, opp2], margin=50)
        print(f"Win {i+1}: mu={target.mu:.2f}, PR={target.mu*2:.1f}")
        
    # 8 losses
    for i in range(8):
        teammate = TrueSkillRating(25.0, 8.333)
        opp1 = TrueSkillRating(25.0, 8.333)
        opp2 = TrueSkillRating(25.0, 8.333)
        # Use teammate_protect with a low-rated partner to see if it helps
        teammate.mu = 10.0 
        weighted_update_trueskill([opp1, opp2], [target, teammate], margin=50)
        print(f"Loss {i+1}: mu={target.mu:.2f}, PR={target.mu*2:.1f}")

if __name__ == "__main__":
    simulate()
