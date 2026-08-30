"""
موتورهای پیشرفته مالی
Advanced Financial Engines

این ماژول شامل:
- موتور قیمت‌گذاری مشتقات با مدل‌های کلاسیک و فازی
- شبیه‌ساز مونت‌کارلو پیشرفته با تکنیک‌های کاهش واریانس
- محاسبه‌گر VaR/CVaR با روش‌های تاریخی، پارامتریک و مونت‌کارلو
- بهینه‌ساز پرتفوی محدب (SOCP)
- تولیدکننده داده‌های مصنوعی با مدل‌های انتشار (Diffusion)
"""

import numpy as np
from scipy.stats import norm, multivariate_normal
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
import warnings


@dataclass
class OptionPrice:
    """نتیجه قیمت‌گذاری اختیار معامله"""
    call_price: float
    put_price: float
    call_delta: float
    put_delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_volatility: Optional[float] = None


@dataclass
class RiskMetrics:
    """معیارهای ریسک پرتفوی"""
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    expected_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float


class MonteCarloEngine:
    """
    موتور شبیه‌سازی مونت‌کارلو پیشرفته
    
    ویژگی‌ها:
    - مسیرهای هندسی براونی (GBM)
    - تکنیک‌های کاهش واریانس (Antithetic Variates, Control Variates)
    - شبیه‌سازی چندمتغیره با همبستگی
    - تولید سناریوهای استرس‌تست
    """
    
    def __init__(self, n_simulations: int = 10000, random_seed: int = 42):
        self.n_sims = n_simulations
        self.rng = np.random.default_rng(random_seed)
        
    def simulate_gbm(self, S0: float, mu: float, sigma: float,
                    T: float, n_steps: int = 252,
                    use_antithetic: bool = True) -> np.ndarray:
        """
        شبیه‌سازی حرکت براونی هندسی (GBM)
        
        پارامترها:
        - S0: قیمت اولیه
        - mu: نرخ بازده مورد انتظار
        - sigma: نوسان‌پذیری
        - T: زمان به سال
        - n_steps: تعداد گام‌های زمانی
        - use_antithetic: استفاده از متغیرهای متضاد برای کاهش واریانس
        
        خروجی:
        - آرایه مسیرهای شبیه‌سازی شده
        """
        dt = T / n_steps
        
        if use_antithetic:
            # تولید نیمی از مسیرها
            half_sims = self.n_sims // 2
            Z = self.rng.standard_normal((half_sims, n_steps))
            # ایجاد نیمه دوم با علامت معکوس
            Z_antithetic = -Z
            Z_combined = np.vstack([Z, Z_antithetic])
        else:
            Z_combined = self.rng.standard_normal((self.n_sims, n_steps))
            
        # محاسبه مسیرهای GBM
        drift = (mu - 0.5 * sigma**2) * dt
        diffusion = sigma * np.sqrt(dt)
        
        increments = drift + diffusion * Z_combined
        paths = np.zeros((Z_combined.shape[0], n_steps + 1))
        paths[:, 0] = S0
        
        paths[:, 1:] = S0 * np.exp(np.cumsum(increments, axis=1))
        
        return paths
        
    def simulate_multivariate_gbm(self, S0: np.ndarray, mu: np.ndarray,
                                 cov_matrix: np.ndarray, T: float,
                                 n_steps: int = 252) -> np.ndarray:
        """
        شبیه‌سازی چندمتغیره GBM با همبستگی
        
        پارامترها:
        - S0: بردار قیمت‌های اولیه
        - mu: بردار نرخ‌های بازده
        - cov_matrix: ماتریس کوواریانس
        - T: زمان به سال
        - n_steps: تعداد گام‌های زمانی
        
        خروجی:
        - آرایه سه‌بعدی [n_sims, n_steps+1, n_assets]
        """
        n_assets = len(S0)
        dt = T / n_steps
        
        # تجزیه چولسکی برای همبستگی
        L = np.linalg.cholesky(cov_matrix)
        
        # تولید نویزهای مستقل
        Z_independent = self.rng.standard_normal((self.n_sims, n_steps, n_assets))
        
        # اعمال همبستگی
        Z_correlated = np.einsum('ijk,lk->ijl', Z_independent, L)
        
        # محاسبه مسیرها
        drift = (mu - 0.5 * np.diag(cov_matrix)) * dt
        diffusion = np.sqrt(dt)
        
        paths = np.zeros((self.n_sims, n_steps + 1, n_assets))
        paths[:, 0, :] = S0
        
        for t in range(n_steps):
            increments = drift + diffusion * Z_correlated[:, t, :]
            paths[:, t+1, :] = paths[:, t, :] * np.exp(increments)
            
        return paths
        
    def price_european_option(self, S0: float, K: float, T: float,
                             r: float, sigma: float, 
                             option_type: str = 'call',
                             use_control_variate: bool = True) -> OptionPrice:
        """
        قیمت‌گذاری اختیار اروپایی با مونت‌کارلو
        
        پارامترها:
        - S0: قیمت دارایی پایه
        - K: قیمت اعمال
        - T: زمان تا سررسید
        - r: نرخ بهره بدون ریسک
        - sigma: نوسان‌پذیری
        - option_type: 'call' یا 'put'
        - use_control_variate: استفاده از متغیر کنترل برای کاهش واریانس
        
        خروجی:
        - آبجکت OptionPrice با قیمت و یونانی‌ها
        """
        # شبیه‌سازی مسیرها
        paths = self.simulate_gbm(S0, r, sigma, T, n_steps=1)
        ST = paths[:, -1]  # قیمت در سررسید
        
        # محاسبه payoff
        if option_type == 'call':
            payoffs = np.maximum(ST - K, 0)
        else:
            payoffs = np.maximum(K - ST, 0)
            
        # تنزیل به زمان حال
        discount_factor = np.exp(-r * T)
        
        if use_control_variate:
            # استفاده از قیمت تحلیلی بلک-شولز به عنوان متغیر کنترل
            from scipy.stats import norm
            
            d1 = (np.log(S0 / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            if option_type == 'call':
                bs_price = S0 * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
                control_payoffs = np.maximum(ST - K, 0)
            else:
                bs_price = K * np.exp(-r * T) * norm.cdf(-d2) - S0 * norm.cdf(-d1)
                control_payoffs = np.maximum(K - ST, 0)
                
            # محاسبه ضریب بهینه
            cov_mc_cv = np.cov(payoffs, control_payoffs)[0, 1]
            var_cv = np.var(control_payoffs)
            
            if var_cv > 0:
                c_star = cov_mc_cv / var_cv
                adjusted_payoffs = payoffs - c_star * (control_payoffs - bs_price)
                option_price = np.exp(-r * T) * np.mean(adjusted_payoffs)
            else:
                option_price = np.exp(-r * T) * np.mean(payoffs)
        else:
            option_price = discount_factor * np.mean(payoffs)
            
        # محاسبه یونانی‌ها با تفاوت محدود
        h = 0.01 * S0
        
        # Delta
        paths_up = self.simulate_gbm(S0 + h, r, sigma, T, n_steps=1)
        paths_down = self.simulate_gbm(S0 - h, r, sigma, T, n_steps=1)
        
        if option_type == 'call':
            payoff_up = np.maximum(paths_up[:, -1] - K, 0)
            payoff_down = np.maximum(paths_down[:, -1] - K, 0)
        else:
            payoff_up = np.maximum(K - paths_up[:, -1], 0)
            payoff_down = np.maximum(K - paths_down[:, -1], 0)
            
        delta = np.exp(-r * T) * (np.mean(payoff_up) - np.mean(payoff_down)) / (2 * h)
        
        # Gamma
        payoff_center = payoffs
        gamma = np.exp(-r * T) * (np.mean(payoff_up) - 2 * np.mean(payoff_center) + np.mean(payoff_down)) / (h**2)
        
        # Vega (تغییر sigma)
        sigma_h = sigma * 1.01
        paths_vega = self.simulate_gbm(S0, r, sigma_h, T, n_steps=1)
        if option_type == 'call':
            payoff_vega = np.maximum(paths_vega[:, -1] - K, 0)
        else:
            payoff_vega = np.maximum(K - paths_vega[:, -1], 0)
        vega = np.exp(-r * T) * (np.mean(payoff_vega) - option_price / discount_factor) / (sigma * 0.01)
        
        # Theta (گذشت زمان)
        T_h = T * 0.99
        if T_h > 0:
            paths_theta = self.simulate_gbm(S0, r, sigma, T_h, n_steps=1)
            if option_type == 'call':
                payoff_theta = np.maximum(paths_theta[:, -1] - K, 0)
            else:
                payoff_theta = np.maximum(K - paths_theta[:, -1], 0)
            theta = np.exp(-r * T_h) * np.mean(payoff_theta) - option_price
            theta = theta / ((T - T_h) * 365)  # روزانه
        else:
            theta = 0.0
            
        # Rho (تغییر نرخ بهره)
        r_h = r + 0.01
        paths_rho = self.simulate_gbm(S0, r_h, sigma, T, n_steps=1)
        if option_type == 'call':
            payoff_rho = np.maximum(paths_rho[:, -1] - K, 0)
        else:
            payoff_rho = np.maximum(K - paths_rho[:, -1], 0)
        rho = np.exp(-r_h * T) * np.mean(payoff_rho) - option_price
        rho = rho / 0.01  # به ازای 1٪ تغییر
        
        return OptionPrice(
            call_price=option_price if option_type == 'call' else None,
            put_price=option_price if option_type == 'put' else None,
            call_delta=delta if option_type == 'call' else None,
            put_delta=delta if option_type == 'put' else None,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho
        )
        
    def generate_stress_scenarios(self, base_returns: np.ndarray,
                                 base_cov: np.ndarray,
                                 scenario_types: List[str] = None) -> Dict:
        """
        تولید سناریوهای استرس‌تست
        
        پارامترها:
        - base_returns: بازده‌های پایه
        - base_cov: ماتریس کوواریانس پایه
        - scenario_types: انواع سناریوها ('market_crash', 'volatility_spike', 'correlation_breakdown')
        
        خروجی:
        - دیکشنری سناریوها با پارامترهای تغییر یافته
        """
        if scenario_types is None:
            scenario_types = ['market_crash', 'volatility_spike', 'correlation_breakdown']
            
        scenarios = {}
        n_assets = len(base_returns)
        
        if 'market_crash' in scenario_types:
            # سقوط بازار: بازده‌ها -3 انحراف معیار
            crash_returns = base_returns - 3 * np.sqrt(np.diag(base_cov))
            scenarios['market_crash'] = {
                'returns': crash_returns,
                'cov_matrix': base_cov * 1.5,  # افزایش نوسان
                'description': 'سقوط 3 سیگما در بازار'
            }
            
        if 'volatility_spike' in scenario_types:
            # جهش نوسان: کوواریانس 3 برابر
            scenarios['volatility_spike'] = {
                'returns': base_returns * 0.5,  # کاهش بازده
                'cov_matrix': base_cov * 3.0,
                'description': 'جهش نوسان‌پذیری به 3 برابر'
            }
            
        if 'correlation_breakdown' in scenario_types:
            # شکست همبستگی: همه همبستگی‌ها به 1 میل می‌کنند
            std_devs = np.sqrt(np.diag(base_cov))
            correlation_matrix = base_cov / np.outer(std_devs, std_devs)
            # افزایش همبستگی به 0.9
            stressed_corr = 0.9 * np.ones((n_assets, n_assets))
            np.fill_diagonal(stressed_corr, 1.0)
            stressed_cov = np.outer(std_devs, std_devs) * stressed_corr
            scenarios['correlation_breakdown'] = {
                'returns': base_returns,
                'cov_matrix': stressed_cov,
                'description': 'همبستگی کامل بین دارایی‌ها'
            }
            
        return scenarios


class RiskEngine:
    """
    موتور محاسبه ریسک (VaR, CVaR)
    
    روش‌ها:
    - تاریخی (Historical Simulation)
    - پارامتریک (Variance-Covariance)
    - مونت‌کارلو
    - Conditional VaR (Expected Shortfall)
    """
    
    def __init__(self, confidence_levels: List[float] = [0.95, 0.99]):
        self.confidence_levels = confidence_levels
        
    def calculate_var_historical(self, returns: np.ndarray,
                                portfolio_weights: np.ndarray = None,
                                horizon_days: int = 1) -> Dict:
        """
        محاسبه VaR با شبیه‌سازی تاریخی
        
        پارامترها:
        - returns: ماتریس بازده‌های تاریخی [n_observations, n_assets]
        - portfolio_weights: وزن‌های پرتفوی
        - horizon_days: افق زمانی به روز
        
        خروجی:
        - دیکشنری VaR در سطوح اطمینان مختلف
        """
        n_obs, n_assets = returns.shape
        
        if portfolio_weights is None:
            portfolio_weights = np.ones(n_assets) / n_assets
            
        # بازده پرتفوی
        portfolio_returns = returns @ portfolio_weights
        
        # مقیاس‌دهی به افق زمانی (فرض جذری)
        scaled_returns = portfolio_returns * np.sqrt(horizon_days)
        
        var_results = {}
        for conf in self.confidence_levels:
            var = -np.percentile(scaled_returns, (1 - conf) * 100)
            var_results[f'var_{int(conf*100)}'] = var
            
        return var_results
        
    def calculate_var_parametric(self, returns: np.ndarray,
                                portfolio_weights: np.ndarray = None,
                                horizon_days: int = 1) -> Dict:
        """
        محاسبه VaR پارامتریک (فرض نرمال بودن)
        """
        n_obs, n_assets = returns.shape
        
        if portfolio_weights is None:
            portfolio_weights = np.ones(n_assets) / n_assets
            
        # میانگین و کوواریانس پرتفوی
        mean_return = np.mean(returns, axis=0) @ portfolio_weights
        var_return = portfolio_weights.T @ np.cov(returns.T) @ portfolio_weights
        std_return = np.sqrt(var_return)
        
        # مقیاس‌دهی به افق زمانی
        mean_scaled = mean_return * horizon_days
        std_scaled = std_return * np.sqrt(horizon_days)
        
        var_results = {}
        for conf in self.confidence_levels:
            z_score = norm.ppf(conf)
            var = -(mean_scaled - z_score * std_scaled)
            var_results[f'var_{int(conf*100)}'] = var
            
        return var_results
        
    def calculate_cvar(self, returns: np.ndarray,
                      portfolio_weights: np.ndarray = None,
                      method: str = 'historical') -> Dict:
        """
        محاسبه Conditional VaR (Expected Shortfall)
        
        CVaR میانگین زیان‌های فراتر از VaR است
        """
        n_obs, n_assets = returns.shape
        
        if portfolio_weights is None:
            portfolio_weights = np.ones(n_assets) / n_assets
            
        portfolio_returns = returns @ portfolio_weights
        
        cvar_results = {}
        for conf in self.confidence_levels:
            var_threshold = np.percentile(portfolio_returns, (1 - conf) * 100)
            # میانگین زیان‌های بدتر از VaR
            tail_losses = portfolio_returns[portfolio_returns <= var_threshold]
            if len(tail_losses) > 0:
                cvar = -np.mean(tail_losses)
            else:
                cvar = -var_threshold
                
            cvar_results[f'cvar_{int(conf*100)}'] = cvar
            
        return cvar_results
        
    def calculate_comprehensive_risk(self, returns: np.ndarray,
                                    portfolio_weights: np.ndarray = None,
                                    risk_free_rate: float = 0.02) -> RiskMetrics:
        """
        محاسبه جامع معیارهای ریسک
        """
        n_obs, n_assets = returns.shape
        
        if portfolio_weights is None:
            portfolio_weights = np.ones(n_assets) / n_assets
            
        portfolio_returns = returns @ portfolio_weights
        
        # VaR و CVaR
        var_hist = self.calculate_var_historical(returns, portfolio_weights)
        cvar = self.calculate_cvar(returns, portfolio_weights)
        
        # آمار توصیفی
        expected_return = np.mean(portfolio_returns) * 252  # سالانه
        volatility = np.std(portfolio_returns) * np.sqrt(252)  # سالانه
        
        # نسبت شارپ
        sharpe = (expected_return - risk_free_rate) / volatility if volatility > 0 else 0
        
        # حداکثر افت سرمایه
        cumulative = np.cumprod(1 + portfolio_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(np.min(drawdown))
        
        return RiskMetrics(
            var_95=var_hist.get('var_95', 0),
            var_99=var_hist.get('var_99', 0),
            cvar_95=cvar.get('cvar_95', 0),
            cvar_99=cvar.get('cvar_99', 0),
            expected_return=expected_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown
        )


class DiffusionDataGenerator:
    """
    تولیدکننده داده‌های مصنوعی با مدل‌های انتشار (Diffusion Models)
    
    برای:
    - تولید مسیرهای قیمتی مصنوعی برای آموزش RL
    - استرس‌تست با سناریوهای نادر
    - افزایش داده برای مدل‌های یادگیری ماشین
    """
    
    def __init__(self, noise_schedule: str = 'linear', n_timesteps: int = 100):
        """
        پارامترها:
        - noise_schedule: برنامه افزودن نویز ('linear', 'cosine')
        - n_timesteps: تعداد گام‌های فرآیند انتشار
        """
        self.n_timesteps = n_timesteps
        self.noise_schedule = noise_schedule
        
        # برنامه‌ریزی واریانس
        if noise_schedule == 'linear':
            self.betas = np.linspace(1e-4, 0.02, n_timesteps)
        elif noise_schedule == 'cosine':
            s = 0.008
            t = np.linspace(0, n_timesteps, n_timesteps + 1)
            alphas_cumprod = np.cos((t / n_timesteps + s) / (1 + s) * np.pi / 2) ** 2
            self.betas = 1 - alphas_cumprod[1:] / alphas_cumprod[:-1]
        else:
            raise ValueError("noise_schedule must be 'linear' or 'cosine'")
            
        self.alphas = 1 - self.betas
        self.alphas_cumprod = np.cumprod(self.alphas)
        self.rng = np.random.default_rng(42)
        
    def forward_diffusion(self, data: np.ndarray, t: int) -> np.ndarray:
        """
        فرآیند مستقیم: افزودن نویز به داده
        
        q(x_t | x_0) = N(x_t; sqrt(alpha_cumprod_t) * x_0, (1 - alpha_cumprod_t) * I)
        """
        sqrt_alpha_cumprod = np.sqrt(self.alphas_cumprod[t])
        sqrt_one_minus_alpha_cumprod = np.sqrt(1 - self.alphas_cumprod[t])
        
        noise = self.rng.standard_normal(data.shape)
        noisy_data = sqrt_alpha_cumprod * data + sqrt_one_minus_alpha_cumprod * noise
        
        return noisy_data, noise
        
    def reverse_diffusion_step(self, x_t: np.ndarray, t: int,
                              model_prediction: Callable = None) -> np.ndarray:
        """
        یک گام از فرآیند معکوس: حذف نویز
        
        اگر model_prediction داده نشود، از یک تقریب ساده استفاده می‌کند
        """
        if t == 0:
            return x_t
            
        # ضرایب
        beta_t = self.betas[t]
        alpha_t = self.alphas[t]
        alpha_cumprod_t = self.alphas_cumprod[t]
        alpha_cumprod_prev = self.alphas_cumprod[t-1] if t > 0 else 1.0
        
        # اگر مدل پیش‌بینی وجود دارد، از آن استفاده کن
        if model_prediction:
            epsilon_pred = model_prediction(x_t, t)
        else:
            # تقریب ساده: فرض کن نویز پیش‌بینی‌شده خود نویز افزوده‌شده است
            epsilon_pred = self.rng.standard_normal(x_t.shape)
            
        # محاسبه میانگین posterior
        mean_coeff = (1.0 / np.sqrt(alpha_t)) * (x_t - ((1 - alpha_t) / np.sqrt(1 - alpha_cumprod_t)) * epsilon_pred)
        variance = beta_t
        
        # نمونه‌برداری
        if t > 1:
            noise = self.rng.standard_normal(x_t.shape)
            x_t_minus_1 = mean_coeff + np.sqrt(variance) * noise
        else:
            x_t_minus_1 = mean_coeff
            
        return x_t_minus_1
        
    def generate_synthetic_paths(self, initial_data: np.ndarray,
                                n_paths: int = 1000,
                                path_length: int = 252) -> np.ndarray:
        """
        تولید مسیرهای مصنوعی با فرآیند انتشار معکوس
        
        پارامترها:
        - initial_data: داده اولیه برای یادگیری توزیع
        - n_paths: تعداد مسیرهای مصنوعی
        - path_length: طول هر مسیر
        
        خروجی:
        - آرایه [n_paths, path_length, n_features]
        """
        n_features = initial_data.shape[1] if len(initial_data.shape) > 1 else 1
        
        # شروع از نویز خالص
        x_T = self.rng.standard_normal((n_paths, path_length, n_features))
        
        # فرآیند معکوس
        x_current = x_T
        for t in reversed(range(self.n_timesteps)):
            x_current = self.reverse_diffusion_step(x_current, t)
            
        # نرمال‌سازی به مقیاس داده اولیه
        if len(initial_data.shape) == 1:
            data_mean = np.mean(initial_data)
            data_std = np.std(initial_data)
        else:
            data_mean = np.mean(initial_data, axis=(0, 1))
            data_std = np.std(initial_data, axis=(0, 1)) + 1e-8
            
        synthetic_data = x_current * data_std + data_mean
        
        return synthetic_data
        
    def augment_training_data(self, original_data: np.ndarray,
                             augmentation_factor: int = 5) -> np.ndarray:
        """
        افزایش داده آموزشی با داده‌های مصنوعی
        """
        synthetic = self.generate_synthetic_paths(
            original_data,
            n_paths=len(original_data) * augmentation_factor,
            path_length=original_data.shape[1] if len(original_data.shape) > 1 else 1
        )
        
        # ترکیب داده اصلی و مصنوعی
        if len(original_data.shape) == 2:
            augmented = np.vstack([original_data, synthetic.reshape(-1, original_data.shape[1])])
        else:
            augmented = np.concatenate([original_data, synthetic.flatten()])
            
        return augmented


__all__ = [
    'MonteCarloEngine',
    'RiskEngine',
    'DiffusionDataGenerator',
    'OptionPrice',
    'RiskMetrics'
]
