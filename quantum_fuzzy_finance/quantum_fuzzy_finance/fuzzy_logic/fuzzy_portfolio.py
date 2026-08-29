"""
Fuzzy Portfolio Optimization Module

بهینه‌سازی پرتفوی با استفاده از اعداد فازی
جایگزینی مدل مارکوویتز با رویکرد فازی برای بازارهای با داده‌های محدود
"""

import numpy as np
from typing import Dict, List, Tuple
from scipy.optimize import minimize

# Import from same package
from . import FuzzyNumber, TriangularMF, TrapezoidalMF


class FuzzyPortfolioOptimizer:
    """
    بهینه‌سازی پرتفوی با پارامترهای فازی
    
    این کلاس از اعداد فازی مثلثی/ذوزنقه‌ای برای نمایش بازده و ریسک
    استفاده می‌کند و به دنبال بیشینه‌سازی امکان رسیدن به بازده مورد نظر است.
    """
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        Args:
            risk_free_rate: نرخ بازده بدون ریسک
        """
        self.risk_free_rate = risk_free_rate
    
    def triangular_fuzzy_number(self, a: float, b: float, c: float) -> FuzzyNumber:
        """ایجاد عدد فازی مثلثی"""
        return FuzzyNumber(fuzzy_type='triangular', params=(a, b, c))
    
    def trapezoidal_fuzzy_number(self, a: float, b: float, c: float, d: float) -> FuzzyNumber:
        """ایجاد عدد فازی ذوزنقه‌ای"""
        return FuzzyNumber(fuzzy_type='trapezoidal', params=(a, b, c, d))
    
    def fuzzy_expected_return(self, 
                              returns_history: np.ndarray,
                              uncertainty_factor: float = 0.1) -> FuzzyNumber:
        """
        محاسبه بازده مورد انتظار فازی از داده‌های تاریخی
        
        Args:
            returns_history: آرایه بازده‌های تاریخی
            uncertainty_factor: ضریب عدم قطعیت برای ایجاد بازه فازی
            
        Returns:
            عدد فازی مثلثی برای بازده مورد انتظار
        """
        mean_return = np.mean(returns_history)
        std_return = np.std(returns_history)
        
        # ایجاد عدد فازی مثلثی
        a = mean_return - uncertainty_factor * std_return
        b = mean_return
        c = mean_return + uncertainty_factor * std_return
        
        return self.triangular_fuzzy_number(a, b, c)
    
    def fuzzy_risk(self, 
                   covariance_matrix: np.ndarray,
                   uncertainty_factor: float = 0.15) -> FuzzyNumber:
        """
        محاسبه ریسک فازی از ماتریس کوواریانس
        
        Args:
            covariance_matrix: ماتریس کوواریانس دارایی‌ها
            uncertainty_factor: ضریب عدم قطعیت
            
        Returns:
            عدد فازی مثلثی برای ریسک
        """
        # ریسک پرتفوی برابر است با واریانس (قطر ماتریس کوواریانس میانگین گرفته شود)
        avg_variance = np.mean(np.diag(covariance_matrix))
        risk = np.sqrt(avg_variance)
        
        a = risk * (1 - uncertainty_factor)
        b = risk
        c = risk * (1 + uncertainty_factor)
        
        return self.triangular_fuzzy_number(a, b, c)
    
    def fuzzy_sharpe_ratio(self, 
                           fuzzy_return: FuzzyNumber,
                           fuzzy_risk: FuzzyNumber) -> FuzzyNumber:
        """
        محاسبه نسبت شارپ فازی
        
        Args:
            fuzzy_return: بازده فازی
            fuzzy_risk: ریسک فازی
            
        Returns:
            نسبت شارپ فازی
        """
        # محاسبه نسبت شارپ برای هر نقطه از اعداد فازی
        if fuzzy_return.fuzzy_type == 'triangular' and fuzzy_risk.fuzzy_type == 'triangular':
            a_return, b_return, c_return = fuzzy_return.params
            a_risk, b_risk, c_risk = fuzzy_risk.params
            
            # نسبت شارپ فازی (تقریبی)
            sharpe_a = (a_return - self.risk_free_rate) / c_risk  # بدترین حالت
            sharpe_b = (b_return - self.risk_free_rate) / b_risk  # حالت محتمل
            sharpe_c = (c_return - self.risk_free_rate) / a_risk  # بهترین حالت
            
            return self.triangular_fuzzy_number(sharpe_a, sharpe_b, sharpe_c)
        
        raise NotImplementedError("Only triangular fuzzy numbers supported for now")
    
    def optimize_fuzzy_portfolio(self,
                                  expected_returns: List[FuzzyNumber],
                                  covariance_matrix: np.ndarray,
                                  target_return: FuzzyNumber = None,
                                  max_weight: float = 0.3,
                                  min_weight: float = 0.0) -> Dict:
        """
        بهینه‌سازی پرتفوی با قیود فازی
        
        Args:
            expected_returns: لیست بازده‌های فازی مورد انتظار برای هر دارایی
            covariance_matrix: ماتریس کوواریانس
            target_return: بازده هدف فازی (اختیاری)
            max_weight: حداکثر وزن هر دارایی
            min_weight: حداقل وزن هر دارایی
            
        Returns:
            دیکشنری شامل وزن‌های بهینه و معیارهای عملکرد
        """
        n_assets = len(expected_returns)
        
        # استخراج مقادیر محتمل (b در اعداد فازی مثلثی)
        crisp_returns = np.array([er.params[1] if er.fuzzy_type == 'triangular' 
                                   else er.params[1] for er in expected_returns])
        
        def portfolio_return(weights):
            return np.sum(weights * crisp_returns)
        
        def portfolio_risk(weights):
            return np.sqrt(weights.T @ covariance_matrix @ weights)
        
        def neg_sharpe(weights):
            ret = portfolio_return(weights)
            risk = portfolio_risk(weights)
            return -(ret - self.risk_free_rate) / risk
        
        # قیود
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        
        if target_return is not None:
            target_val = target_return.params[1]
            constraints.append({
                'type': 'ineq',
                'fun': lambda w: portfolio_return(w) - target_val
            })
        
        bounds = tuple((min_weight, max_weight) for _ in range(n_assets))
        
        # مقدار اولیه مساوی
        x0 = np.ones(n_assets) / n_assets
        
        # بهینه‌سازی
        result = minimize(neg_sharpe, x0, method='SLSQP', bounds=bounds, 
                         constraints=constraints)
        
        if not result.success:
            print(f"Warning: Optimization failed - {result.message}")
        
        optimal_weights = result.x
        
        # محاسبه معیارهای عملکرد
        opt_return = portfolio_return(optimal_weights)
        opt_risk = portfolio_risk(optimal_weights)
        opt_sharpe = (opt_return - self.risk_free_rate) / opt_risk
        
        return {
            'weights': optimal_weights,
            'expected_return': opt_return,
            'risk': opt_risk,
            'sharpe_ratio': opt_sharpe,
            'optimization_success': result.success
        }
    
    def possibility_maximization(self,
                                  weights: np.ndarray,
                                  expected_returns: List[FuzzyNumber],
                                  target_level: float) -> float:
        """
        محاسبه امکان (Possibility) رسیدن به سطح بازده هدف
        
        Args:
            weights: وزن‌های پرتفوی
            expected_returns: بازده‌های فازی
            target_level: سطح بازده هدف
            
        Returns:
            میزان امکان بین ۰ و ۱
        """
        # محاسبه بازده فازی پرتفوی
        portfolio_params = [0.0, 0.0, 0.0]
        
        for i, weight in enumerate(weights):
            er = expected_returns[i]
            if er.fuzzy_type == 'triangular':
                a, b, c = er.params
                portfolio_params[0] += weight * a
                portfolio_params[1] += weight * b
                portfolio_params[2] += weight * c
        
        # محاسبه تابع عضویت در نقطه هدف
        a_port, b_port, c_port = portfolio_params
        
        if target_level <= a_port or target_level >= c_port:
            return 0.0
        elif a_port < target_level <= b_port:
            return (target_level - a_port) / (b_port - a_port)
        else:  # b_port < target_level < c_port
            return (c_port - target_level) / (c_port - b_port)


# مثال استفاده
if __name__ == "__main__":
    print("=== Fuzzy Portfolio Optimization Example ===\n")
    
    optimizer = FuzzyPortfolioOptimizer(risk_free_rate=0.02)
    
    # داده‌های نمونه برای ۴ دارایی
    np.random.seed(42)
    n_assets = 4
    n_periods = 60
    
    # تولید بازده‌های تصادفی
    returns_data = np.random.normal(0.01, 0.05, (n_periods, n_assets))
    
    # محاسبه بازده‌های فازی مورد انتظار
    expected_returns_fuzzy = []
    for i in range(n_assets):
        fuzzy_ret = optimizer.fuzzy_expected_return(
            returns_data[:, i],
            uncertainty_factor=0.2
        )
        expected_returns_fuzzy.append(fuzzy_ret)
        print(f"Asset {i+1}: Expected Return (fuzzy) = {fuzzy_ret}")
    
    # ماتریس کوواریانس
    cov_matrix = np.cov(returns_data.T)
    print(f"\nCovariance Matrix Shape: {cov_matrix.shape}")
    
    # بهینه‌سازی پرتفوی
    result = optimizer.optimize_fuzzy_portfolio(
        expected_returns_fuzzy,
        cov_matrix,
        max_weight=0.4,
        min_weight=0.05
    )
    
    print("\n=== Optimization Results ===")
    print(f"Weights: {[f'{w:.2%}' for w in result['weights']]}")
    print(f"Expected Return: {result['expected_return']:.2%}")
    print(f"Risk: {result['risk']:.2%}")
    print(f"Sharpe Ratio: {result['sharpe_ratio']:.3f}")
    print(f"Optimization Success: {result['optimization_success']}")
    
    # محاسبه امکان رسیدن به بازده هدف
    target = 0.015  # ۱.۵٪ بازده ماهانه هدف
    possibility = optimizer.possibility_maximization(
        result['weights'],
        expected_returns_fuzzy,
        target
    )
    print(f"\nPossibility of achieving {target:.1%} return: {possibility:.2%}")
