"""
Quantum-Fuzzy Finance Framework - Main Package

این چارچوب جامع، تلفیقی از علوم گذشته، حال و آینده فایننس کمی را ارائه می‌دهد:
- منطق فازی برای عدم قطعیت‌های کیفی
- یادگیری تقویتی برای تصمیم‌گیری متوالی
- بهینه‌سازی پیشرفته پرتفوی
- تحلیل توپولوژیک داده (TDA)
- استنتاج علی (Causal Inference)
- و سایر متدولوژی‌های نوین
"""

__version__ = "1.0.0"
__author__ = "Quantum-Fuzzy Finance Team"

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name in ['FuzzyNumber', 'TriangularMF', 'TrapezoidalMF', 'GaussianMF', 
                'FuzzyVariable', 'FuzzyInferenceSystem', 'FuzzyCreditScorer']:
        from fuzzy_logic import (
            FuzzyNumber, TriangularMF, TrapezoidalMF, GaussianMF,
            FuzzyVariable, FuzzyInferenceSystem, FuzzyCreditScorer
        )
        return locals()[name]
    elif name == 'FuzzyPortfolioOptimizer':
        from fuzzy_logic.fuzzy_portfolio import FuzzyPortfolioOptimizer
        return FuzzyPortfolioOptimizer
    elif name in ['MarketEnvironment', 'RLOptimalExecution']:
        from ml_agents.rl_execution import MarketEnvironment, RLOptimalExecution
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_framework_info():
    """دریافت اطلاعات چارچوب"""
    return {
        'name': 'Quantum-Fuzzy Finance Framework',
        'version': __version__,
        'description': 'چارچوب جامع مالی کمی با تلفیق منطق فازی و یادگیری ماشین',
        'modules': [
            'fuzzy_logic - منطق فازی برای امتیازدهی اعتباری و بهینه‌سازی پرتفوی',
            'ml_agents - عامل‌های یادگیری تقویتی برای اجرای سفارش',
            'risk_management - مدیریت ریسک پیشرفته',
            'models - مدل‌های قیمت‌گذاری و پیش‌بینی',
            'utils - ابزارهای کمکی'
        ],
        'capabilities': [
            'امتیازدهی اعتباری فازی',
            'بهینه‌سازی پرتفوی با پارامترهای فازی',
            'قیمت‌گذاری مشتقات با مدل بلک-شولز فازی',
            'معاملات الگوریتمی با قوانین فازی',
            'شبکه عصبی-فازی برای پیش‌بینی ورشکستگی',
            'اجرای بهینه سفارش با یادگیری تقویتی',
            'تحلیل شبکه‌های مالی با نظریه گراف',
            'استنتاج علی برای تشخیص اثرات واقعی',
            'تحلیل توپولوژیک برای تغییر رژیم بازار'
        ]
    }


if __name__ == "__main__":
    info = get_framework_info()
    print(f"\n{info['name']} v{info['version']}")
    print(f"\n{info['description']}\n")
    print("Available Modules:")
    for module in info['modules']:
        print(f"  - {module}")
    print("\nKey Capabilities:")
    for cap in info['capabilities']:
        print(f"  • {cap}")
    print()
