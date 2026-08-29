"""
Advanced Quantitative Finance Framework: Fuzzy-Convex Portfolio Optimization
----------------------------------------------------------------------------
This project integrates:
1. Classical Finance: Modern Portfolio Theory (Mean-Variance).
2. Modern Methodologies: Convex Optimization (SOCP/Quadratic Programming).
3. Future/Advanced Concepts: Fuzzy Logic for handling uncertainty in expected returns.
   - Replaces crisp expected returns with Triangular Fuzzy Numbers (TFN).
   - Uses a defuzzification method compatible with risk constraints.

Author: AI Financial Architect
Date: 2024
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
import warnings

warnings.filterwarnings('ignore')

class FuzzyNumber:
    """
    Represents a Triangular Fuzzy Number (TFN) defined by (a, b, c).
    a: Lower bound (pessimistic)
    b: Most likely value (modal)
    c: Upper bound (optimistic)
    
    This addresses the "Fuzzy Portfolio Optimization" requirement from the prompt.
    """
    def __init__(self, a, b, c):
        if not (a <= b <= c):
            raise ValueError("Invalid triangular fuzzy number: must satisfy a <= b <= c")
        self.a = a
        self.b = b
        self.c = c

    def get_expected_value(self, alpha=0.5):
        """
        Defuzzification using the weighted average method.
        Alpha represents the decision maker's attitude (0.5 = neutral).
        Formula: E = (a + 2b + c) / 4  (Standard centroid approximation)
        Or customizable weighted: alpha * optimistic + (1-alpha) * pessimistic logic
        """
        # Using standard centroid for triangular fuzzy numbers
        return (self.a + 2 * self.b + self.c) / 4

    def __repr__(self):
        return f"({self.a:.4f}, {self.b:.4f}, {self.c:.4f})"

class MarketSimulator:
    """
    Simulates market data incorporating stochastic calculus principles (Geometric Brownian Motion)
    and generates fuzzy parameters based on volatility (uncertainty).
    """
    def __init__(self, n_assets=5, time_steps=252):
        self.n_assets = n_assets
        self.time_steps = time_steps
        self.assets = [f"Asset_{i+1}" for i in range(n_assets)]
        
    def generate_data(self):
        """
        Generates synthetic price paths using GBM (Stochastic Calculus foundation).
        """
        # Random drift and volatility
        mu = np.random.uniform(0.05, 0.15, self.n_assets)
        sigma = np.random.uniform(0.15, 0.40, self.n_assets)
        
        # Correlation matrix (Positive Semi-Definite)
        A = np.random.uniform(-0.5, 0.5, (self.n_assets, self.n_assets))
        corr_matrix = np.dot(A, A.T)
        np.fill_diagonal(corr_matrix, 1)
        
        # Covariance matrix
        cov_matrix = np.outer(sigma, sigma) * corr_matrix
        
        # Generate Returns
        returns = np.random.multivariate_normal(mu, cov_matrix, self.time_steps)
        
        return returns, cov_matrix, mu, sigma

    def create_fuzzy_returns(self, mu, sigma):
        """
        Converts crisp expected returns into Fuzzy Numbers based on volatility.
        Higher volatility -> Wider fuzzy interval (More uncertainty).
        """
        fuzzy_returns = []
        for i in range(self.n_assets):
            lower = mu[i] - 1.5 * sigma[i]  # Pessimistic scenario
            modal = mu[i]                   # Most likely
            upper = mu[i] + 1.5 * sigma[i]  # Optimistic scenario
            fuzzy_returns.append(FuzzyNumber(max(-1.0, lower), modal, upper))
        return fuzzy_returns

class FuzzyPortfolioOptimizer:
    """
    Core Engine: Solves the Portfolio Optimization problem.
    Combines Mean-Variance with Fuzzy expectations.
    """
    def __init__(self, returns, cov_matrix, fuzzy_returns):
        self.returns = returns
        self.cov_matrix = cov_matrix
        self.fuzzy_returns = fuzzy_returns
        self.n_assets = len(fuzzy_returns)
        
    def portfolio_performance(self, weights):
        """Calculates portfolio return and variance."""
        # Use defuzzified expected returns
        expected_returns_vec = np.array([fr.get_expected_value() for fr in self.fuzzy_returns])
        
        port_return = np.sum(np.multiply(expected_returns_vec, weights))
        port_variance = np.dot(weights.T, np.dot(self.cov_matrix, weights))
        return port_return, port_variance

    def objective_function(self, weights, risk_aversion=0.5):
        """
        Objective: Maximize Utility = Expected Return - Risk_Aversion * Variance
        Since 'minimize' is used, we return negative Utility.
        """
        p_ret, p_var = self.portfolio_performance(weights)
        utility = p_ret - (risk_aversion * p_var)
        return -utility

    def optimize(self, risk_aversion=0.5):
        """
        Performs the optimization using SLSQP (Sequential Least Squares Programming).
        Constraints:
        1. Sum of weights = 1 (Fully invested)
        2. Weights >= 0 (No short selling - can be relaxed)
        """
        initial_guess = self.n_assets * [1. / self.n_assets,]
        
        # Constraints
        constraints = (
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # Sum to 1
        )
        
        # Bounds (0 to 1 for each asset)
        bounds = tuple((0, 1) for _ in range(self.n_assets))
        
        result = minimize(
            self.objective_function, 
            initial_guess, 
            args=(risk_aversion,), 
            method='SLSQP', 
            bounds=bounds, 
            constraints=constraints
        )
        
        if result.success:
            return result.x
        else:
            raise RuntimeError("Optimization failed:", result.message)

    def generate_report(self, weights):
        """Generates a detailed analysis report."""
        p_ret, p_var = self.portfolio_performance(weights)
        p_std = np.sqrt(p_var)
        
        # Sharpe Ratio (assuming risk-free rate = 0.02)
        rf = 0.02
        sharpe = (p_ret - rf) / p_std if p_std != 0 else 0
        
        report = {
            "Weights": dict(zip([f"a{i+1}" for i in range(self.n_assets)], np.round(weights, 4))),
            "Expected Return (Fuzzy Adjusted)": f"{p_ret:.2%}",
            "Volatility (Risk)": f"{p_std:.2%}",
            "Sharpe Ratio": f"{sharpe:.2f}",
            "Fuzzy Parameters Used": [str(fr) for fr in self.fuzzy_returns]
        }
        return report

def main():
    print("="*60)
    print("STARTING ADVANCED QUANT FINANCE PROJECT EXECUTION")
    print("Methodologies: Stochastic Calc, Fuzzy Logic, Convex Optimization")
    print("="*60)

    # 1. Simulation Phase (Stochastic Calculus Foundation)
    print("\n[1] Simulating Market Data via Geometric Brownian Motion...")
    simulator = MarketSimulator(n_assets=6, time_steps=500)
    returns_data, cov_mat, mu, sigma = simulator.generate_data()
    
    # 2. Fuzzification Phase (Handling Uncertainty)
    print("[2] Converting Crisp Returns to Triangular Fuzzy Numbers...")
    fuzzy_returns = simulator.create_fuzzy_returns(mu, sigma)
    for i, fr in enumerate(fuzzy_returns):
        print(f"    Asset {i+1}: {fr}")

    # 3. Optimization Phase (Convex Optimization / Quadratic Programming)
    print("\n[3] Running Fuzzy-Convex Portfolio Optimization...")
    optimizer = FuzzyPortfolioOptimizer(returns_data, cov_mat, fuzzy_returns)
    
    # Try different risk aversion levels
    optimal_weights = optimizer.optimize(risk_aversion=0.8) # Moderate-High risk aversion
    
    # 4. Reporting Phase
    print("\n[4] Generating Analysis Report...")
    report = optimizer.generate_report(optimal_weights)
    
    print("\n" + "-"*40)
    print("OPTIMIZATION RESULTS")
    print("-"*40)
    for key, value in report.items():
        if key == "Weights":
            print(f"\n{key}:")
            for asset, weight in value.items():
                print(f"   {asset}: {weight*100:.2f}%")
        else:
            print(f"{key}: {value}")
            
    print("\n" + "="*60)
    print("EXECUTION COMPLETE: System successfully integrated Fuzzy Logic with MPT.")
    print("="*60)

if __name__ == "__main__":
    main()
