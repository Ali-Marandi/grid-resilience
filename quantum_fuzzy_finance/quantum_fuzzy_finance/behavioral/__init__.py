"""
Behavioral Finance Module for Quantum-Fuzzy Finance Framework

This module implements behavioral finance models including:
- Prospect Theory (Kahneman-Tversky)
- Disposition Effect modeling
- Herding behavior and information cascades
- Overconfidence bias quantification
- Neuroeconomics-inspired decision models
"""

import numpy as np
from typing import Dict, Tuple, Optional, List, Callable
from dataclasses import dataclass
from scipy.stats import norm


@dataclass
class ProspectTheoryParameters:
    """Parameters for Prospect Theory value function"""
    alpha: float = 0.88  # Curvature parameter for gains
    beta: float = 0.88   # Curvature parameter for losses
    lambda_: float = 2.25  # Loss aversion coefficient
    reference_point: float = 0.0  # Reference point for gains/losses


@dataclass 
class InvestorProfile:
    """Behavioral profile of an investor"""
    loss_aversion: float = 2.25
    risk_aversion_gains: float = 0.88
    risk_aversion_losses: float = 0.88
    overconfidence_level: float = 0.5
    herding_tendency: float = 0.3
    disposition_effect_strength: float = 0.6


class ProspectTheoryValueFunction:
    """
    Implementation of Kahneman-Tversky Prospect Theory Value Function
    
    The value function is:
    - Concave for gains (risk aversion)
    - Convex for losses (risk seeking)
    - Steeper for losses than gains (loss aversion)
    
    v(x) = x^alpha if x >= 0
    v(x) = -lambda * (-x)^beta if x < 0
    """
    
    def __init__(self, params: Optional[ProspectTheoryParameters] = None):
        """
        Initialize Prospect Theory value function
        
        Args:
            params: Model parameters (uses defaults if None)
        """
        self.params = params or ProspectTheoryParameters()
    
    def calculate_value(self, outcome: float) -> float:
        """
        Calculate subjective value of an outcome
        
        Args:
            outcome: Objective outcome (gain or loss relative to reference)
            
        Returns:
            Subjective value according to prospect theory
        """
        x = outcome - self.params.reference_point
        
        if x >= 0:
            return x ** self.params.alpha
        else:
            return -self.params.lambda_ * ((-x) ** self.params.beta)
    
    def calculate_certainty_equivalent(self, 
                                      gamble_outcomes: List[float],
                                      probabilities: List[float]) -> float:
        """
        Calculate certainty equivalent of a gamble
        
        Args:
            gamble_outcomes: Possible outcomes of the gamble
            probabilities: Probabilities of each outcome
            
        Returns:
            Certainty equivalent (sure amount equally preferred to gamble)
        """
        # Calculate expected prospect theory value
        expected_value = sum(
            p * self.calculate_value(outcome)
            for outcome, p in zip(gamble_outcomes, probabilities)
        )
        
        # Find certainty equivalent by inverting value function
        if expected_value >= 0:
            ce = expected_value ** (1 / self.params.alpha)
        else:
            ce = -((-expected_value / self.params.lambda_) ** (1 / self.params.beta))
        
        return ce
    
    def estimate_parameters_from_choices(self,
                                        choices: List[Tuple[List[float], List[float], int]],
                                        method: str = 'MLE') -> ProspectTheoryParameters:
        """
        Estimate prospect theory parameters from observed choices
        
        Args:
            choices: List of (outcomes_A, probs_A, chosen_option) tuples
                    where chosen_option is 0 for A, 1 for B
            method: Estimation method ('MLE' or 'GMM')
            
        Returns:
            Estimated parameters
        """
        from scipy.optimize import minimize
        
        def log_likelihood(params_array):
            alpha, beta, lambda_, ref_point = params_array
            
            # Ensure parameters are in valid ranges
            if alpha <= 0 or alpha > 1 or beta <= 0 or beta > 1 or lambda_ <= 0:
                return 1e10
            
            ll = 0
            for outcomes_A, probs_A, chosen in choices:
                # Calculate values for option A
                value_A = sum(
                    p * (outcome ** alpha if outcome >= ref_point 
                         else -lambda_ * ((-outcome) ** beta))
                    for outcome, p in zip(outcomes_A, probs_A)
                )
                
                # Assume option B is the expected value (risk-neutral)
                value_B = sum(o * p for o, p in zip(outcomes_A, probs_A))
                
                # Logistic choice probability
                prob_choose_A = 1 / (1 + np.exp(-(value_A - value_B)))
                
                if chosen == 0:
                    ll += np.log(prob_choose_A + 1e-10)
                else:
                    ll += np.log(1 - prob_choose_A + 1e-10)
            
            return -ll  # Negative for minimization
        
        # Optimize
        initial_params = [0.88, 0.88, 2.25, 0.0]
        bounds = [(0.1, 1.0), (0.1, 1.0), (0.5, 5.0), (-10, 10)]
        
        result = minimize(log_likelihood, initial_params, bounds=bounds, method='L-BFGS-B')
        
        return ProspectTheoryParameters(
            alpha=result.x[0],
            beta=result.x[1],
            lambda_=result.x[2],
            reference_point=result.x[3]
        )


class DispositionEffectModel:
    """
    Model of the Disposition Effect
    
    The tendency to:
    - Sell winning stocks too early
    - Hold losing stocks too long
    
    Based on Shefrin & Statman (1985)
    """
    
    def __init__(self, strength: float = 0.6):
        """
        Initialize disposition effect model
        
        Args:
            strength: Strength of disposition effect (0-1)
        """
        self.strength = strength
        self.prospect_theory = ProspectTheoryValueFunction()
    
    def probability_of_selling(self, 
                              purchase_price: float,
                              current_price: float,
                              holding_period: int = 30) -> float:
        """
        Calculate probability of selling given gain/loss
        
        Args:
            purchase_price: Original purchase price
            current_price: Current market price
            holding_period: Days held
            
        Returns:
            Probability of selling (0-1)
        """
        gain_loss_ratio = (current_price - purchase_price) / purchase_price
        
        # Base probability increases with gains, decreases with losses
        base_prob = 0.5 + 0.3 * np.tanh(2 * gain_loss_ratio)
        
        # Adjust for disposition effect strength
        adjusted_prob = base_prob + self.strength * 0.2 * np.sign(gain_loss_ratio)
        
        # Holding period effect (longer holding -> less likely to sell losers)
        if gain_loss_ratio < 0:
            holding_adjustment = -0.01 * min(holding_period, 365) / 30
            adjusted_prob += holding_adjustment
        
        return max(0.0, min(1.0, adjusted_prob))
    
    def simulate_portfolio_turnover(self,
                                   positions: List[Dict[str, float]],
                                   market_returns: np.ndarray) -> Dict[str, float]:
        """
        Simulate portfolio turnover under disposition effect
        
        Args:
            positions: List of dicts with 'purchase_price', 'current_price', 'shares'
            market_returns: Array of daily market returns
            
        Returns:
            Dictionary with turnover statistics
        """
        total_trades = 0
        winning_trades = 0
        losing_trades = 0
        premature_winning_sales = 0
        delayed_losing_sales = 0
        
        for position in positions:
            purchase_price = position['purchase_price']
            shares = position['shares']
            
            for i, ret in enumerate(market_returns):
                current_price = purchase_price * (1 + ret) ** (i + 1)
                hold_period = i + 1
                
                sell_prob = self.probability_of_selling(
                    purchase_price, current_price, hold_period
                )
                
                if np.random.random() < sell_prob:
                    total_trades += 1
                    gain_loss = current_price - purchase_price
                    
                    if gain_loss > 0:
                        winning_trades += 1
                        # Check if sale was premature (small gain)
                        if gain_loss / purchase_price < 0.05:
                            premature_winning_sales += 1
                    else:
                        losing_trades += 1
                        # Check if sale was delayed (large loss after long hold)
                        if hold_period > 60 and gain_loss / purchase_price < -0.1:
                            delayed_losing_sales += 1
                    
                    break  # Position sold
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'premature_winning_sales': premature_winning_sales,
            'delayed_losing_sales': delayed_losing_sales,
            'win_rate': winning_trades / max(total_trades, 1),
            'disposition_ratio': (premature_winning_sales + delayed_losing_sales) / max(total_trades, 1)
        }


class HerdingBehaviorModel:
    """
    Model of herding behavior and information cascades
    
    Based on Bikhchandani, Hirshleifer & Welch (1992)
    """
    
    def __init__(self, signal_precision: float = 0.6):
        """
        Initialize herding model
        
        Args:
            signal_precision: Precision of private signals (0.5-1.0)
        """
        self.signal_precision = signal_precision
    
    def simulate_information_cascade(self,
                                    true_state: bool,
                                    num_agents: int = 100) -> Dict[str, any]:
        """
        Simulate information cascade among agents
        
        Args:
            true_state: True state of the world (True=good, False=bad)
            num_agents: Number of sequential agents
            
        Returns:
            Dictionary with cascade simulation results
        """
        decisions = []
        private_signals = []
        cascade_started = False
        cascade_start_index = -1
        cascade_direction = None
        
        public_belief = 0.5  # Initial prior
        
        for i in range(num_agents):
            # Generate private signal
            if true_state:
                signal = np.random.random() < self.signal_precision
            else:
                signal = np.random.random() >= self.signal_precision
            private_signals.append(signal)
            
            # Agent observes previous decisions
            if i == 0:
                # First agent follows private signal
                decision = signal
            else:
                # Calculate posterior belief
                prev_decisions = decisions.copy()
                num_buy = sum(prev_decisions)
                num_sell = len(prev_decisions) - num_buy
                
                # Check if cascade has started
                if abs(num_buy - num_sell) >= 2:
                    cascade_started = True
                    if cascade_start_index < 0:
                        cascade_start_index = i
                        cascade_direction = num_buy > num_sell
                    # Follow the crowd regardless of private signal
                    decision = num_buy > num_sell
                else:
                    # Combine public belief with private signal
                    if signal:
                        posterior = public_belief * self.signal_precision
                    else:
                        posterior = public_belief * (1 - self.signal_precision)
                    
                    decision = posterior > 0.5
            
            decisions.append(decision)
            
            # Update public belief (simplified)
            if decision:
                public_belief = min(0.99, public_belief + 0.05)
            else:
                public_belief = max(0.01, public_belief - 0.05)
        
        return {
            'decisions': decisions,
            'private_signals': private_signals,
            'cascade_started': cascade_started,
            'cascade_start_index': cascade_start_index,
            'cascade_direction': cascade_direction,
            'final_majority': sum(decisions) > len(decisions) / 2,
            'correct_decision': (sum(decisions) > len(decisions) / 2) == true_state
        }
    
    def calculate_cascade_probability(self,
                                     signal_precision: float,
                                     num_agents: int) -> float:
        """
        Calculate probability of incorrect cascade forming
        
        Args:
            signal_precision: Precision of private signals
            num_agents: Number of agents
            
        Returns:
            Probability of incorrect cascade
        """
        # Analytical approximation
        # Probability increases when signal precision is low
        base_prob = (1 - signal_precision) ** 2
        
        # More agents -> higher chance of cascade
        agent_factor = 1 - (0.95 ** num_agents)
        
        return base_prob * agent_factor


class OverconfidenceModel:
    """
    Model of overconfidence bias in trading
    
    Based on Barberis & Odean (2000-2001) findings
    """
    
    def __init__(self, overconfidence_level: float = 0.5):
        """
        Initialize overconfidence model
        
        Args:
            overconfidence_level: Level of overconfidence (0-1)
                                0 = perfectly calibrated
                                1 = maximally overconfident
        """
        self.overconfidence_level = overconfidence_level
    
    def inflate_confidence_interval(self,
                                   mean_estimate: float,
                                   true_std: float,
                                   perceived_reduction: Optional[float] = None) -> Tuple[float, float]:
        """
        Calculate overconfident confidence interval
        
        Args:
            mean_estimate: Point estimate
            true_std: True standard deviation
            perceived_reduction: How much agent thinks they've reduced uncertainty
            
        Returns:
            (perceived_mean, perceived_std) under overconfidence
        """
        if perceived_reduction is None:
            perceived_reduction = self.overconfidence_level * 0.5
        
        # Overconfident agents underestimate uncertainty
        perceived_std = true_std * (1 - perceived_reduction)
        
        # May also have biased mean estimate
        bias = self.overconfidence_level * true_std * 0.2
        
        return mean_estimate + bias, max(perceived_std, true_std * 0.1)
    
    def calculate_excessive_trading(self,
                                   true_skill: float,
                                   perceived_skill: Optional[float] = None) -> float:
        """
        Calculate ratio of actual to optimal trading volume
        
        Args:
            true_skill: True predictive skill (Sharpe ratio)
            perceived_skill: Perceived skill (if None, inflated by overconfidence)
            
        Returns:
            Ratio of actual to optimal trading volume
        """
        if perceived_skill is None:
            perceived_skill = true_skill * (1 + self.overconfidence_level)
        
        # Excessive trading increases with overconfidence
        excess_ratio = 1 + (perceived_skill - true_skill) * 2
        
        return min(excess_ratio, 5.0)  # Cap at 5x
    
    def estimate_performance_drag(self,
                                 base_return: float,
                                 turnover_rate: float,
                                 transaction_cost: float = 0.001) -> float:
        """
        Estimate performance drag from overconfident trading
        
        Args:
            base_return: Return without excessive trading
            turnover_rate: Annual turnover rate
            transaction_cost: Cost per trade
            
        Returns:
            Net return after transaction costs
        """
        # Higher turnover from overconfidence -> more costs
        total_costs = turnover_rate * transaction_cost
        
        net_return = base_return - total_costs
        
        return net_return


class NeuroeconomicsDecisionModel:
    """
    Neuroeconomics-inspired decision model
    
    Incorporates findings from fMRI studies:
    - Nucleus accumbens activation (reward anticipation)
    - Insula activation (loss aversion/fear)
    - Prefrontal cortex (cognitive control)
    """
    
    def __init__(self, 
                 reward_sensitivity: float = 1.0,
                 loss_sensitivity: float = 1.5,
                 cognitive_control: float = 0.7):
        """
        Initialize neuroeconomics model
        
        Args:
            reward_sensitivity: Sensitivity to potential rewards (nucleus accumbens)
            loss_sensitivity: Sensitivity to potential losses (insula)
            cognitive_control: Ability to override emotional responses (PFC)
        """
        self.reward_sensitivity = reward_sensitivity
        self.loss_sensitivity = loss_sensitivity
        self.cognitive_control = cognitive_control
    
    def calculate_choice_probability(self,
                                    expected_gain: float,
                                    expected_loss: float,
                                    probability_gain: float,
                                    probability_loss: float) -> float:
        """
        Calculate probability of taking a risky action
        
        Args:
            expected_gain: Expected gain amount
            expected_loss: Expected loss amount  
            probability_gain: Probability of gain
            probability_loss: Probability of loss
            
        Returns:
            Probability of choosing to take the risk (0-1)
        """
        # Emotional valuation (subcortical)
        reward_signal = self.reward_sensitivity * expected_gain * probability_gain
        loss_signal = self.loss_sensitivity * expected_loss * probability_loss
        
        emotional_value = reward_signal - loss_signal
        
        # Cognitive evaluation (prefrontal)
        expected_value = (expected_gain * probability_gain - 
                         expected_loss * probability_loss)
        
        # Integration with cognitive control
        final_value = (self.cognitive_control * expected_value + 
                      (1 - self.cognitive_control) * emotional_value)
        
        # Convert to probability via sigmoid
        choice_prob = 1 / (1 + np.exp(-final_value))
        
        return choice_prob
    
    def simulate_market_sentiment(self,
                                  news_flow: List[float],
                                  num_agents: int = 1000) -> Dict[str, float]:
        """
        Simulate aggregate market sentiment from individual neural responses
        
        Args:
            news_flow: Sequence of news items (positive=negative numbers)
            num_agents: Number of simulated agents
            
        Returns:
            Dictionary with sentiment metrics
        """
        agent_responses = []
        
        for _ in range(num_agents):
            # Vary neural parameters across agents
            agent = NeuroeconomicsDecisionModel(
                reward_sensitivity=np.random.normal(1.0, 0.2),
                loss_sensitivity=np.random.normal(1.5, 0.3),
                cognitive_control=np.random.normal(0.7, 0.15)
            )
            
            # Aggregate response to news flow
            total_response = 0
            for news in news_flow[-10:]:  # Last 10 news items
                if news > 0:
                    resp = agent.calculate_choice_probability(
                        news, 0, 0.6, 0
                    )
                else:
                    resp = -agent.calculate_choice_probability(
                        0, abs(news), 0, 0.6
                    )
                total_response += resp
            
            agent_responses.append(total_response / len(news_flow[-10:]))
        
        return {
            'mean_sentiment': np.mean(agent_responses),
            'sentiment_volatility': np.std(agent_responses),
            'bullish_fraction': np.mean([r > 0 for r in agent_responses]),
            'bearish_fraction': np.mean([r < 0 for r in agent_responses]),
            'sentiment_polarization': np.std(agent_responses) / (np.mean(np.abs(agent_responses)) + 0.01)
        }


def create_behavioral_model(model_type: str = 'prospect_theory', **kwargs):
    """
    Factory function to create behavioral finance models
    
    Args:
        model_type: Type of model
        **kwargs: Additional arguments
        
    Returns:
        Initialized model instance
    """
    if model_type == 'prospect_theory':
        params = kwargs.get('params')
        return ProspectTheoryValueFunction(params)
    elif model_type == 'disposition_effect':
        strength = kwargs.get('strength', 0.6)
        return DispositionEffectModel(strength)
    elif model_type == 'herding':
        precision = kwargs.get('signal_precision', 0.6)
        return HerdingBehaviorModel(precision)
    elif model_type == 'overconfidence':
        level = kwargs.get('overconfidence_level', 0.5)
        return OverconfidenceModel(level)
    elif model_type == 'neuroeconomics':
        return NeuroeconomicsDecisionModel(**kwargs)
    else:
        raise ValueError(f"Unknown model type: {model_type}")
