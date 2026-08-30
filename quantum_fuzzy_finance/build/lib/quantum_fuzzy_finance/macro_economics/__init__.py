"""
Macro Economics Module for Quantum-Fuzzy Finance Framework

This module implements advanced macroeconomic models including:
- DSGE (Dynamic Stochastic General Equilibrium) models
- Taylor Rule for central bank policy prediction
- Phillips Curve analysis
- Economic shock propagation modeling
"""

import numpy as np
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
from scipy.optimize import minimize


@dataclass
class DSGEParameters:
    """Parameters for New Keynesian DSGE model"""
    beta: float = 0.99  # Discount factor
    kappa: float = 0.17  # Slope of Phillips curve
    sigma: float = 1.0  # Risk aversion coefficient
    phi_pi: float = 1.5  # Taylor rule inflation coefficient
    phi_y: float = 0.5  # Taylor rule output gap coefficient
    rho_a: float = 0.9  # Technology shock persistence
    rho_r: float = 0.8  # Monetary policy shock persistence
    sigma_a: float = 0.01  # Technology shock std dev
    sigma_r: float = 0.003  # Monetary policy shock std dev


@dataclass
class EconomicState:
    """State variables in the DSGE model"""
    output_gap: float = 0.0
    inflation: float = 0.02
    interest_rate: float = 0.02
    technology_shock: float = 0.0
    monetary_shock: float = 0.0


class TaylorRuleModel:
    """
    Implementation of Taylor Rule for central bank policy prediction
    
    The Taylor Rule determines the target interest rate based on:
    - Inflation gap (deviation from target)
    - Output gap (deviation from potential output)
    
    Formula: i = r* + π + 0.5(π - π*) + 0.5(y - y*)
    """
    
    def __init__(self, 
                 equilibrium_rate: float = 0.02,
                 inflation_target: float = 0.02,
                 inflation_coeff: float = 0.5,
                 output_coeff: float = 0.5):
        """
        Initialize Taylor Rule model
        
        Args:
            equilibrium_rate: Real equilibrium interest rate (r*)
            inflation_target: Target inflation rate (π*)
            inflation_coeff: Coefficient on inflation gap
            output_coeff: Coefficient on output gap
        """
        self.r_star = equilibrium_rate
        self.pi_target = inflation_target
        self.phi_pi = inflation_coeff
        self.phi_y = output_coeff
    
    def calculate_target_rate(self, 
                             current_inflation: float, 
                             output_gap: float) -> float:
        """
        Calculate target interest rate using Taylor Rule
        
        Args:
            current_inflation: Current inflation rate
            output_gap: Output gap (actual - potential) / potential
            
        Returns:
            Target nominal interest rate
        """
        inflation_gap = current_inflation - self.pi_target
        target_rate = (self.r_star + current_inflation + 
                      self.phi_pi * inflation_gap + 
                      self.phi_y * output_gap)
        return max(0.0, target_rate)  # Zero lower bound
    
    def implied_rule_from_data(self, 
                               rates: np.ndarray, 
                               inflation: np.ndarray, 
                               output_gaps: np.ndarray) -> Dict[str, float]:
        """
        Estimate implicit Taylor Rule coefficients from historical data
        
        Args:
            rates: Historical interest rates
            inflation: Historical inflation rates
            output_gaps: Historical output gaps
            
        Returns:
            Dictionary with estimated coefficients
        """
        # Simple OLS estimation
        X = np.column_stack([
            np.ones(len(inflation)),
            inflation - self.pi_target,
            output_gaps
        ])
        y = rates
        
        # Solve normal equations
        coeffs = np.linalg.lstsq(X, y, rcond=None)[0]
        
        return {
            'equilibrium_rate': coeffs[0] - np.mean(inflation),
            'inflation_coeff': coeffs[1],
            'output_coeff': coeffs[2]
        }


class PhillipsCurve:
    """
    New Keynesian Phillips Curve implementation
    
    Models inflation as a function of:
    - Expected future inflation
    - Current output gap
    - Cost-push shocks
    """
    
    def __init__(self, 
                 slope: float = 0.17,
                 discount_factor: float = 0.99,
                 persistence: float = 0.8):
        """
        Initialize Phillips Curve model
        
        Args:
            slope: Sensitivity of inflation to output gap (kappa)
            discount_factor: Discount factor for forward-looking expectations
            persistence: Persistence of cost-push shocks
        """
        self.kappa = slope
        self.beta = discount_factor
        self.rho = persistence
    
    def calculate_inflation(self, 
                           expected_inflation: float,
                           output_gap: float,
                           cost_shock: float = 0.0) -> float:
        """
        Calculate current inflation using New Keynesian Phillips Curve
        
        π_t = β * E_t[π_{t+1}] + κ * y_t + u_t
        
        Args:
            expected_inflation: Expected future inflation
            output_gap: Current output gap
            cost_shock: Cost-push shock
            
        Returns:
            Current inflation rate
        """
        inflation = (self.beta * expected_inflation + 
                    self.kappa * output_gap + 
                    cost_shock)
        return inflation
    
    def estimate_slope(self, 
                      inflation_data: np.ndarray,
                      output_gaps: np.ndarray,
                      expected_inflation: Optional[np.ndarray] = None) -> float:
        """
        Estimate Phillips Curve slope from historical data
        
        Args:
            inflation_data: Historical inflation rates
            output_gaps: Historical output gaps
            expected_inflation: Expected inflation (if available)
            
        Returns:
            Estimated slope parameter (kappa)
        """
        if expected_inflation is None:
            # Use adaptive expectations as proxy
            expected_inflation = np.roll(inflation_data, 1)[1:]
            inflation_data = inflation_data[1:]
            output_gaps = output_gaps[1:]
        
        # Simple regression
        X = expected_inflation
        y = inflation_data - self.kappa * output_gaps
        
        slope = np.cov(X, y)[0, 1] / np.var(X) if np.var(X) > 0 else 0
        return slope
    
    def is_flatting(self, 
                   recent_slope: float,
                   historical_slope: float,
                   threshold: float = 0.3) -> bool:
        """
        Check if Phillips Curve is flattening
        
        Args:
            recent_slope: Recent estimated slope
            historical_slope: Historical average slope
            threshold: Threshold for considering curve as "flat"
            
        Returns:
            True if curve is significantly flatter than historical
        """
        return recent_slope < historical_slope * (1 - threshold)


class DSGEModel:
    """
    Dynamic Stochastic General Equilibrium Model
    
    Implements a basic New Keynesian DSGE model with:
    - Household optimization (IS curve)
    - Firm optimization (Phillips curve)
    - Central bank policy (Taylor rule)
    - Exogenous shocks (technology, monetary policy)
    """
    
    def __init__(self, params: Optional[DSGEParameters] = None):
        """
        Initialize DSGE model
        
        Args:
            params: Model parameters (uses defaults if None)
        """
        self.params = params or DSGEParameters()
        self.taylor_rule = TaylorRuleModel(
            equilibrium_rate=self.params.beta,
            inflation_coeff=self.params.phi_pi,
            output_coeff=self.params.phi_y
        )
        self.phillips_curve = PhillipsCurve(
            slope=self.params.kappa,
            discount_factor=self.params.beta
        )
    
    def simulate(self, 
                periods: int = 100,
                initial_state: Optional[EconomicState] = None) -> Dict[str, np.ndarray]:
        """
        Simulate the DSGE model forward in time
        
        Args:
            periods: Number of periods to simulate
            initial_state: Initial economic state
            
        Returns:
            Dictionary with time series of all variables
        """
        state = initial_state or EconomicState()
        
        # Initialize arrays
        output_gaps = np.zeros(periods)
        inflations = np.zeros(periods)
        interest_rates = np.zeros(periods)
        tech_shocks = np.zeros(periods)
        monetary_shocks = np.zeros(periods)
        
        # Set initial values
        output_gaps[0] = state.output_gap
        inflations[0] = state.inflation
        interest_rates[0] = state.interest_rate
        tech_shocks[0] = state.technology_shock
        monetary_shocks[0] = state.monetary_shock
        
        # Simulate forward
        for t in range(1, periods):
            # Generate shocks
            tech_shocks[t] = (self.params.rho_a * tech_shocks[t-1] + 
                            self.params.sigma_a * np.random.normal())
            monetary_shocks[t] = (self.params.rho_r * monetary_shocks[t-1] + 
                                self.params.sigma_r * np.random.normal())
            
            # IS curve (simplified): output gap depends on real interest rate
            real_rate = interest_rates[t-1] - inflations[t-1]
            output_gaps[t] = (0.8 * output_gaps[t-1] - 
                            0.5 * (real_rate - self.params.beta) + 
                            tech_shocks[t])
            
            # Phillips curve: inflation depends on output gap and expectations
            expected_inflation = inflations[t-1]  # Adaptive expectations
            inflations[t] = self.phillips_curve.calculate_inflation(
                expected_inflation, output_gaps[t], monetary_shocks[t]
            )
            
            # Taylor rule: interest rate policy
            interest_rates[t] = self.taylor_rule.calculate_target_rate(
                inflations[t], output_gaps[t]
            )
        
        return {
            'output_gap': output_gaps,
            'inflation': inflations,
            'interest_rate': interest_rates,
            'technology_shock': tech_shocks,
            'monetary_shock': monetary_shocks
        }
    
    def impulse_response(self, 
                        shock_type: str = 'technology',
                        shock_size: float = 0.01,
                        periods: int = 40) -> Dict[str, np.ndarray]:
        """
        Calculate impulse response functions
        
        Args:
            shock_type: Type of shock ('technology' or 'monetary')
            shock_size: Size of the initial shock
            periods: Number of periods to trace response
            
        Returns:
            Dictionary with impulse response functions
        """
        # Baseline simulation (no shock)
        baseline = self.simulate(periods=periods)
        
        # Shocked simulation
        initial_state = EconomicState()
        if shock_type == 'technology':
            initial_state.technology_shock = shock_size
        elif shock_type == 'monetary':
            initial_state.monetary_shock = shock_size
        
        shocked = self.simulate(periods=periods, initial_state=initial_state)
        
        # Calculate responses (difference from baseline)
        responses = {}
        for key in shocked.keys():
            responses[key] = shocked[key] - baseline[key]
        
        return responses
    
    def calibrate_to_data(self, 
                         data: Dict[str, np.ndarray],
                         method: str = 'GMM') -> DSGEParameters:
        """
        Calibrate model parameters to empirical data
        
        Args:
            data: Dictionary with empirical time series
            method: Calibration method ('GMM' or 'MLE')
            
        Returns:
            Calibrated parameters
        """
        # Simple method of moments calibration
        target_moments = {
            'vol_output': np.std(data['output_gap']),
            'vol_inflation': np.std(data['inflation']),
            'corr_output_inflation': np.corrcoef(
                data['output_gap'], data['inflation']
            )[0, 1]
        }
        
        def objective(params_array):
            # Update parameters
            self.params.kappa = params_array[0]
            self.params.phi_pi = params_array[1]
            self.params.phi_y = params_array[2]
            
            # Simulate model
            sim = self.simulate(periods=len(data['output_gap']))
            
            # Calculate model moments
            model_moments = {
                'vol_output': np.std(sim['output_gap']),
                'vol_inflation': np.std(sim['inflation']),
                'corr_output_inflation': np.corrcoef(
                    sim['output_gap'], sim['inflation']
                )[0, 1]
            }
            
            # Sum of squared deviations
            loss = sum((target_moments[k] - model_moments[k])**2 
                      for k in target_moments.keys())
            return loss
        
        # Optimize
        initial_guess = [self.params.kappa, self.params.phi_pi, self.params.phi_y]
        bounds = [(0.01, 1.0), (1.0, 3.0), (0.1, 1.0)]
        
        result = minimize(objective, initial_guess, bounds=bounds, method='L-BFGS-B')
        
        # Update parameters
        self.params.kappa = result.x[0]
        self.params.phi_pi = result.x[1]
        self.params.phi_y = result.x[2]
        
        return self.params
    
    def assess_market_impact(self, 
                           shock_scenario: Dict[str, float],
                           asset_classes: List[str] = ['equities', 'bonds']) -> Dict[str, float]:
        """
        Assess impact of macroeconomic shocks on different asset classes
        
        Args:
            shock_scenario: Dictionary describing shock scenario
            asset_classes: List of asset classes to analyze
            
        Returns:
            Dictionary with estimated impact on each asset class
        """
        # Run simulation with shock scenario
        initial_state = EconomicState()
        if 'inflation_shock' in shock_scenario:
            initial_state.inflation = shock_scenario['inflation_shock']
        if 'output_shock' in shock_scenario:
            initial_state.output_gap = shock_scenario['output_shock']
        
        sim_results = self.simulate(periods=20, initial_state=initial_state)
        
        # Calculate asset class impacts (simplified mappings)
        impacts = {}
        
        avg_rate_change = np.mean(sim_results['interest_rate'][10:]) - np.mean(sim_results['interest_rate'][:5])
        avg_inflation_change = np.mean(sim_results['inflation'][10:]) - np.mean(sim_results['inflation'][:5])
        avg_output_change = np.mean(sim_results['output_gap'][10:]) - np.mean(sim_results['output_gap'][:5])
        
        if 'equities' in asset_classes:
            # Equities: negatively affected by rate hikes, positively by output growth
            equity_impact = -2.0 * avg_rate_change + 1.5 * avg_output_change
            impacts['equities'] = equity_impact
        
        if 'bonds' in asset_classes:
            # Bonds: negatively affected by rate hikes and inflation
            bond_impact = -5.0 * avg_rate_change - 2.0 * avg_inflation_change
            impacts['bonds'] = bond_impact
        
        return impacts


def create_macro_model(model_type: str = 'DSGE', **kwargs):
    """
    Factory function to create macroeconomic models
    
    Args:
        model_type: Type of model ('DSGE', 'TaylorRule', 'PhillipsCurve')
        **kwargs: Additional arguments for model initialization
        
    Returns:
        Initialized model instance
    """
    if model_type == 'DSGE':
        params = kwargs.get('params')
        return DSGEModel(params)
    elif model_type == 'TaylorRule':
        return TaylorRuleModel(**kwargs)
    elif model_type == 'PhillipsCurve':
        return PhillipsCurve(**kwargs)
    else:
        raise ValueError(f"Unknown model type: {model_type}")
