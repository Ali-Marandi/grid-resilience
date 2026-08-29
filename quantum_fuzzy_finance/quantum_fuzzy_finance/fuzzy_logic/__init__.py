"""
Fuzzy Logic Module for Quantum-Fuzzy Finance Framework

این ماژول پیاده‌سازی منطق فازی برای کاربردهای مالی را ارائه می‌دهد:
- توابع عضویت فازی (مثلثی، ذوزنقه‌ای، گاوسی)
- سیستم استنتاج فازی (FIS)
- اعداد فازی و عملیات روی آن‌ها
"""

import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Union
import skfuzzy as fuzz
from skfuzzy import control as ctrl


class FuzzyNumber:
    """
    کلاس نمایش اعداد فازی
    
    پشتیبانی از اعداد فازی مثلثی و ذوزنقه‌ای
    """
    
    def __init__(self, 
                 fuzzy_type: str = 'triangular',
                 params: Tuple = None):
        """
        مقداردهی اولیه عدد فازی
        
        Args:
            fuzzy_type: نوع تابع عضویت ('triangular', 'trapezoidal')
            params: پارامترهای تابع عضویت
                - triangular: (a, b, c) где a<=b<=c
                - trapezoidal: (a, b, c, d) где a<=b<=c<=d
        """
        self.fuzzy_type = fuzzy_type
        self.params = params
        
        if fuzzy_type == 'triangular':
            self.a, self.b, self.c = params
        elif fuzzy_type == 'trapezoidal':
            self.a, self.b, self.c, self.d = params
    
    def membership(self, x: float) -> float:
        """
        محاسبه درجه عضویت یک مقدار
        
        Args:
            x: مقدار ورودی
            
        Returns:
            درجه عضویت بین ۰ و ۱
        """
        if self.fuzzy_type == 'triangular':
            return self._triangular_membership(x)
        elif self.fuzzy_type == 'trapezoidal':
            return self._trapezoidal_membership(x)
    
    def _triangular_membership(self, x: float) -> float:
        a, b, c = self.params
        if x <= a or x >= c:
            return 0.0
        elif a < x <= b:
            return (x - a) / (b - a)
        else:  # b < x < c
            return (c - x) / (c - b)
    
    def _trapezoidal_membership(self, x: float) -> float:
        a, b, c, d = self.params
        if x <= a or x >= d:
            return 0.0
        elif a < x <= b:
            return (x - a) / (b - a)
        elif b < x < c:
            return 1.0
        else:  # c <= x < d
            return (d - x) / (d - c)
    
    def alpha_cut(self, alpha: float) -> Tuple[float, float]:
        """
        محاسبه برش آلفا
        
        Args:
            alpha: سطح برش (بین ۰ و ۱)
            
        Returns:
            بازه [lower, upper] برش آلفا
        """
        if self.fuzzy_type == 'triangular':
            a, b, c = self.params
            lower = a + alpha * (b - a)
            upper = c - alpha * (c - b)
            return (lower, upper)
        elif self.fuzzy_type == 'trapezoidal':
            a, b, c, d = self.params
            lower = a + alpha * (b - a)
            upper = d - alpha * (d - c)
            return (lower, upper)
    
    def __repr__(self):
        return f"FuzzyNumber({self.fuzzy_type}, {self.params})"


class FuzzyMembershipFunction(ABC):
    """کلاس پایه برای توابع عضویت فازی"""
    
    @abstractmethod
    def membership(self, x: float) -> float:
        pass


class TriangularMF(FuzzyMembershipFunction):
    """تابع عضویت مثلثی"""
    
    def __init__(self, a: float, b: float, c: float):
        self.a, self.b, self.c = a, b, c
    
    def membership(self, x: float) -> float:
        if x <= self.a or x >= self.c:
            return 0.0
        elif self.a < x <= self.b:
            return (x - self.a) / (self.b - self.a)
        else:
            return (self.c - x) / (self.c - self.b)


class TrapezoidalMF(FuzzyMembershipFunction):
    """تابع عضویت ذوزنقه‌ای"""
    
    def __init__(self, a: float, b: float, c: float, d: float):
        self.a, self.b, self.c, self.d = a, b, c, d
    
    def membership(self, x: float) -> float:
        if x <= self.a or x >= self.d:
            return 0.0
        elif self.a < x <= self.b:
            return (x - self.a) / (self.b - self.a)
        elif self.b < x < self.c:
            return 1.0
        else:
            return (self.d - x) / (self.d - self.c)


class GaussianMF(FuzzyMembershipFunction):
    """تابع عضویت گاوسی"""
    
    def __init__(self, mean: float, sigma: float):
        self.mean = mean
        self.sigma = sigma
    
    def membership(self, x: float) -> float:
        return np.exp(-((x - self.mean) ** 2) / (2 * self.sigma ** 2))


class FuzzyVariable:
    """
    متغیر فازی با چندین تابع عضویت
    
    مثال: متغیر "درآمد" با توابع عضویت "کم"، "متوسط"، "زیاد"
    """
    
    def __init__(self, name: str, universe: np.ndarray):
        """
        Args:
            name: نام متغیر
            universe: دامنه تغییرات متغیر
        """
        self.name = name
        self.universe = universe
        self.terms: Dict[str, FuzzyMembershipFunction] = {}
    
    def add_term(self, term_name: str, mf: FuzzyMembershipFunction):
        """افزودن یک_term فازی به متغیر"""
        self.terms[term_name] = mf
    
    def get_membership(self, value: float, term_name: str) -> float:
        """دریافت درجه عضویت یک مقدار در یک_term"""
        if term_name not in self.terms:
            raise ValueError(f"Term '{term_name}' not found")
        return self.terms[term_name].membership(value)


class FuzzyInferenceSystem:
    """
    سیستم استنتاج فازی (FIS)
    
    پشتیبانی از Mamdani و Sugeno
    """
    
    def __init__(self, inference_type: str = 'mamdani'):
        """
        Args:
            inference_type: نوع استنتاج ('mamdani' یا 'sugeno')
        """
        self.inference_type = inference_type
        self.input_vars: Dict[str, FuzzyVariable] = {}
        self.output_vars: Dict[str, FuzzyVariable] = {}
        self.rules: List[Dict] = []
    
    def add_input_variable(self, var: FuzzyVariable):
        """افزودن متغیر ورودی"""
        self.input_vars[var.name] = var
    
    def add_output_variable(self, var: FuzzyVariable):
        """افزودن متغیر خروجی"""
        self.output_vars[var.name] = var
    
    def add_rule(self, antecedents: Dict[str, str], 
                 consequents: Dict[str, str],
                 weight: float = 1.0):
        """
        افزودن قانون فازی
        
        Args:
            antecedents: پیشینه {'variable_name': 'term_name'}
            consequents: نتیجه {'variable_name': 'term_name'}
            weight: وزن قانون
        """
        rule = {
            'antecedents': antecedents,
            'consequents': consequents,
            'weight': weight
        }
        self.rules.append(rule)
    
    def infer(self, input_values: Dict[str, float]) -> Dict[str, float]:
        """
        استنتاج فازی
        
        Args:
            input_values: مقادیر ورودی {'variable_name': value}
            
        Returns:
            مقادیر خروجی پس از defuzzification
        """
        # محاسبه درجه فعال‌سازی هر قانون
        rule_activations = []
        
        for rule in self.rules:
            # محاسبه حداقل درجه عضویت در پیشینه (AND فازی)
            activation_degrees = []
            for var_name, term_name in rule['antecedents'].items():
                var = self.input_vars[var_name]
                degree = var.get_membership(input_values[var_name], term_name)
                activation_degrees.append(degree)
            
            # وزن قانون
            rule_weight = min(activation_degrees) * rule['weight']
            rule_activations.append((rule, rule_weight))
        
        # تجميع خروجی‌ها و Defuzzification
        outputs = {}
        
        for output_var_name, output_var in self.output_vars.items():
            # ایجاد تابع عضویت تجمیع‌شده
            aggregated = np.zeros_like(output_var.universe)
            
            for rule, weight in rule_activations:
                if output_var_name in rule['consequents']:
                    term_name = rule['consequents'][output_var_name]
                    mf = output_var.terms[term_name]
                    
                    # برش تابع عضویت در سطح وزن قانون
                    clipped = np.minimum(weight, 
                                        [mf.membership(x) for x in output_var.universe])
                    aggregated = np.maximum(aggregated, clipped)
            
            # Defuzzification با روش مرکز ثقل (Centroid)
            if np.sum(aggregated) > 0:
                crisp_value = np.sum(output_var.universe * aggregated) / np.sum(aggregated)
            else:
                crisp_value = np.mean(output_var.universe)
            
            outputs[output_var_name] = crisp_value
        
        return outputs


class FuzzyCreditScorer:
    """
    امتیازدهی اعتباری فازی
    
    استفاده از متغیرهای زبانی برای ارزیابی اعتبار
    """
    
    def __init__(self):
        self.fis = FuzzyInferenceSystem(inference_type='mamdani')
        self._setup_system()
    
    def _setup_system(self):
        """تنظیم سیستم استنتاج فازی"""
        
        # متغیرهای ورودی
        income_range = np.linspace(0, 100, 100)  # درآمد نرمال‌شده
        income_var = FuzzyVariable('income', income_range)
        income_var.add_term('low', TrapezoidalMF(0, 0, 20, 40))
        income_var.add_term('medium', TriangularMF(30, 50, 70))
        income_var.add_term('high', TrapezoidalMF(60, 80, 100, 100))
        
        credit_history_range = np.linspace(0, 100, 100)
        credit_var = FuzzyVariable('credit_history', credit_history_range)
        credit_var.add_term('poor', TrapezoidalMF(0, 0, 20, 40))
        credit_var.add_term('fair', TriangularMF(30, 50, 70))
        credit_var.add_term('good', TrapezoidalMF(60, 80, 100, 100))
        
        debt_ratio_range = np.linspace(0, 100, 100)
        debt_var = FuzzyVariable('debt_ratio', debt_ratio_range)
        debt_var.add_term('low', TrapezoidalMF(0, 0, 20, 40))
        debt_var.add_term('medium', TriangularMF(30, 50, 70))
        debt_var.add_term('high', TrapezoidalMF(60, 80, 100, 100))
        
        self.fis.add_input_variable(income_var)
        self.fis.add_input_variable(credit_var)
        self.fis.add_input_variable(debt_var)
        
        # متغیر خروجی: امتیاز اعتباری
        score_range = np.linspace(0, 100, 100)
        score_var = FuzzyVariable('credit_score', score_range)
        score_var.add_term('very_low', TrapezoidalMF(0, 0, 15, 30))
        score_var.add_term('low', TriangularMF(20, 35, 50))
        score_var.add_term('medium', TriangularMF(45, 60, 75))
        score_var.add_term('high', TriangularMF(65, 80, 90))
        score_var.add_term('very_high', TrapezoidalMF(75, 90, 100, 100))
        
        self.fis.add_output_variable(score_var)
        
        # تعریف قوانین
        self._define_rules()
    
    def _define_rules(self):
        """تعریف قوانین استنتاج فازی"""
        
        rules = [
            # درآمد بالا + سابقه خوب + بدهی کم => امتیاز بسیار بالا
            ({'income': 'high', 'credit_history': 'good', 'debt_ratio': 'low'},
             {'credit_score': 'very_high'}, 1.0),
            
            # درآمد بالا + سابقه متوسط + بدهی متوسط => امتیاز بالا
            ({'income': 'high', 'credit_history': 'fair', 'debt_ratio': 'medium'},
             {'credit_score': 'high'}, 0.9),
            
            # درآمد متوسط + سابقه خوب + بدهی کم => امتیاز بالا
            ({'income': 'medium', 'credit_history': 'good', 'debt_ratio': 'low'},
             {'credit_score': 'high'}, 0.85),
            
            # درآمد متوسط + سابقه متوسط + بدهی متوسط => امتیاز متوسط
            ({'income': 'medium', 'credit_history': 'fair', 'debt_ratio': 'medium'},
             {'credit_score': 'medium'}, 1.0),
            
            # درآمد پایین + سابقه ضعیف + بدهی بالا => امتیاز بسیار پایین
            ({'income': 'low', 'credit_history': 'poor', 'debt_ratio': 'high'},
             {'credit_score': 'very_low'}, 1.0),
             
            # درآمد پایین + سابقه متوسط + بدهی بالا => امتیاز پایین
            ({'income': 'low', 'credit_history': 'fair', 'debt_ratio': 'high'},
             {'credit_score': 'low'}, 0.95),
        ]
        
        for antecedents, consequents, weight in rules:
            self.fis.add_rule(antecedents, consequents, weight)
    
    def calculate_credit_score(self, 
                               income_normalized: float,
                               credit_history_normalized: float,
                               debt_ratio_normalized: float) -> float:
        """
        محاسبه امتیاز اعتباری فازی
        
        Args:
            income_normalized: درآمد نرمال‌شده (۰ تا ۱۰۰)
            credit_history_normalized: سابقه اعتباری نرمال‌شده (۰ تا ۱۰۰)
            debt_ratio_normalized: نسبت بدهی نرمال‌شده (۰ تا ۱۰۰)
            
        Returns:
            امتیاز اعتباری (۰ تا ۱۰۰)
        """
        inputs = {
            'income': income_normalized,
            'credit_history': credit_history_normalized,
            'debt_ratio': debt_ratio_normalized
        }
        
        outputs = self.fis.infer(inputs)
        return outputs['credit_score']


# مثال استفاده
if __name__ == "__main__":
    print("=== Fuzzy Credit Scoring Example ===\n")
    
    scorer = FuzzyCreditScorer()
    
    # تست با داده‌های مختلف
    test_cases = [
        (85, 90, 20),   # درآمد بالا، سابقه عالی، بدهی کم
        (50, 60, 50),   # درآمد متوسط، سابقه متوسط، بدهی متوسط
        (20, 30, 80),   # درآمد پایین، سابقه ضعیف، بدهی بالا
        (70, 75, 35),   # درآمد خوب، سابقه خوب، بدهی کم
    ]
    
    for income, credit, debt in test_cases:
        score = scorer.calculate_credit_score(income, credit, debt)
        print(f"Income: {income}, Credit History: {credit}, Debt Ratio: {debt}")
        print(f"  => Credit Score: {score:.2f}\n")
