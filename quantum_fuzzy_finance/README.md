# Quantum-Fuzzy Finance Framework

یک چارچوب جامع مالی کمی که تلفیقی از علوم گذشته، حال و آینده فایننس را ارائه می‌دهد.

## ساختار پروژه

### ۱. علوم پایه (بنیان‌گذاران فایننس کمی)
- **حسابان تصادفی و تئوری مارتینگل**: قیمت‌گذاری پیوسته، لم ایتو
- **تئوری بازی‌ها**: میکرواستراکچر بازار، طراحی مکانیزم
- **اقتصادسنجی کلاسیک و GMM**: کالیبراسیون مدل‌های مالی
- **برنامه‌ریزی خطی**: بهینه‌سازی پرتفوی نسل اول

### ۲. علوم مدرن (محرک‌های فعلی تحول)
- **یادگیری تقویتی (RL)**: اجرای بهینه سفارشات با PPO/DDPG
- **آمار بیزی و بلک-لیترمن**: ترکیب تعادل بازار با دیدگاه‌های مدیر
- **نظریه گراف**: تحلیل شبکه‌های مالی و سرایت ریسک
- **بهینه‌سازی محدب (SOCP)**: پرتفوی با قیود پیچیده
- **PCA و مدل‌های فاکتوری**: استخراج فاکتورهای نهفته

### ۳. علوم پیشرفته (مرزهای آینده)
- **استنتاج علی و Causal ML**: گذار از همبستگی به علیت
- **TDA (تحلیل توپولوژیک داده)**: شناسایی تغییر رژیم بازار
- **مدل‌های مولد و Diffusion**: تولید داده مصنوعی برای استرس‌تست
- **الگوریتم‌های کوانتومی**: QAE برای مونت‌کارلو، QAOA برای بهینه‌سازی
- **تئوری اطلاعات و آنتروپی انتقال**: جریان اطلاعات بین دارایی‌ها
- **یادگیری فدرال**: آموزش مدل بدون اشتراک داده حساس

### ۴. منطق فازی (Fuzzy Logic)
- **امتیازدهی اعتباری فازی**: متغیرهای زبانی به جای آستانه‌های سخت
- **بهینه‌سازی پرتفوی فازی**: اعداد فازی مثلثی/ذوزنقه‌ای
- **بلک-شولز فازی**: نوسان‌پذیری به عنوان بازه فازی
- **معاملات الگوریتمی فازی**: قوانین اگر-آنگاه نرم
- **ANFIS**: سیستم عصبی-فازی تطبیقی
- **Fuzzy AHP/TOPSIS**: ارزش‌گذاری دارایی‌های نامشهود

### ۵. ابزارهای کاربردی
- **سری‌های زمانی**: ARIMA, SARIMA, GARCH, VAR, Cointegration
- **مهندسی مالی**: Black-Scholes, مونت‌کارلو, VaR/CVaR
- **یادگیری ماشین**: LSTM, Transformer, NLP, Anomaly Detection
- **علوم رفتاری**: نظریه چشم‌انداز، اثر تمایل، عصب‌اقتصاد

## نصب و راه‌اندازی

```bash
pip install numpy pandas scipy scikit-learn tensorflow torch networkx cvxpy skfuzzy
pip install arch statsmodels quantlib-python causalml ripser
```

## مثال‌های کاربردی

### ۱. بهینه‌سازی پرتفوی فازی
```python
from fuzzy_logic.fuzzy_portfolio import FuzzyPortfolioOptimizer

optimizer = FuzzyPortfolioOptimizer()
portfolio = optimizer.optimize(returns, covariance, fuzzy_constraints)
```

### ۲. یادگیری تقویتی برای اجرای سفارش
```python
from ml_agents.rl_execution import RLOptimalExecution

agent = RLOptimalExecution(algorithm='PPO')
execution_strategy = agent.train(market_data)
```

### ۳. تحلیل توپولوژیک برای تشخیص تغییر رژیم
```python
from advanced.tda_analysis import TDARegimeDetector

detector = TDARegimeDetector()
regime_change = detector.detect_persistent_homology(price_data)
```

### ۴. قیمت‌گذاری مشتقات با منطق فازی
```python
from fuzzy_logic.fuzzy_black_scholes import FuzzyBlackScholes

model = FuzzyBlackScholes()
price_range = model.price(S, K, T, fuzzy_volatility, risk_free_rate)
```

### ۵. شبکه عصبی-فازی برای پیش‌بینی ورشکستگی
```python
from fuzzy_logic.anfis import ANFISBankruptcyPredictor

predictor = ANFISBankruptcyPredictor()
bankruptcy_prob = predictor.predict(financial_ratios)
```

## مجوز

MIT License
