"""
Comprehensive Test Suite for Quantum-Fuzzy Finance Framework

این فایل تست جامع برای تمام ماژول‌های پیاده‌سازی شده است
"""

import numpy as np
import sys


def test_fuzzy_logic():
    """تست ماژول منطق فازی"""
    print("=" * 60)
    print("Testing Fuzzy Logic Module")
    print("=" * 60)
    
    from fuzzy_logic import (
        FuzzyNumber, TriangularMF, TrapezoidalMF, GaussianMF,
        FuzzyVariable, FuzzyInferenceSystem, FuzzyCreditScorer
    )
    
    # تست اعداد فازی
    print("\n1. Testing Fuzzy Numbers...")
    triangular = FuzzyNumber(fuzzy_type='triangular', params=(10, 20, 30))
    assert triangular.membership(15) > 0, "Triangular MF failed"
    assert triangular.membership(20) == 1.0, "Peak membership should be 1.0"
    print("   ✓ Fuzzy numbers working correctly")
    
    # تست توابع عضویت
    print("\n2. Testing Membership Functions...")
    tri_mf = TriangularMF(0, 50, 100)
    trap_mf = TrapezoidalMF(0, 20, 80, 100)
    gauss_mf = GaussianMF(50, 10)
    
    assert tri_mf.membership(50) == 1.0, "Triangular MF peak failed"
    assert trap_mf.membership(50) == 1.0, "Trapezoidal MF plateau failed"
    assert gauss_mf.membership(50) == 1.0, "Gaussian MF peak failed"
    print("   ✓ All membership functions working")
    
    # تست سیستم استنتاج فازی
    print("\n3. Testing Fuzzy Inference System...")
    fis = FuzzyInferenceSystem(inference_type='mamdani')
    
    universe = np.linspace(0, 100, 100)
    input_var = FuzzyVariable('input', universe)
    input_var.add_term('low', TriangularMF(0, 0, 50))
    input_var.add_term('high', TriangularMF(50, 100, 100))
    
    output_var = FuzzyVariable('output', universe)
    output_var.add_term('low', TriangularMF(0, 0, 50))
    output_var.add_term('high', TriangularMF(50, 100, 100))
    
    fis.add_input_variable(input_var)
    fis.add_output_variable(output_var)
    fis.add_rule({'input': 'low'}, {'output': 'low'})
    fis.add_rule({'input': 'high'}, {'output': 'high'})
    
    result = fis.infer({'input': 75})
    assert 'output' in result, "FIS inference failed"
    print("   ✓ Fuzzy inference system working")
    
    # تست امتیازدهی اعتباری فازی
    print("\n4. Testing Fuzzy Credit Scoring...")
    scorer = FuzzyCreditScorer()
    
    score1 = scorer.calculate_credit_score(90, 90, 10)  # عالی
    score2 = scorer.calculate_credit_score(10, 10, 90)  # ضعیف
    
    assert score1 > score2, "Credit scoring logic failed"
    assert 0 <= score1 <= 100, "Score out of range"
    assert 0 <= score2 <= 100, "Score out of range"
    print(f"   ✓ Credit scoring working (Good: {score1:.1f}, Bad: {score2:.1f})")
    
    print("\n✅ Fuzzy Logic Module: ALL TESTS PASSED\n")
    return True


def test_fuzzy_portfolio():
    """تست ماژول بهینه‌سازی پرتفوی فازی"""
    print("=" * 60)
    print("Testing Fuzzy Portfolio Optimization Module")
    print("=" * 60)
    
    from fuzzy_logic.fuzzy_portfolio import FuzzyPortfolioOptimizer
    
    # ایجاد optimizer
    print("\n1. Initializing FuzzyPortfolioOptimizer...")
    optimizer = FuzzyPortfolioOptimizer(risk_free_rate=0.02)
    print("   ✓ Optimizer initialized")
    
    # تولید داده‌های نمونه
    print("\n2. Generating sample data...")
    np.random.seed(42)
    n_assets = 5
    n_periods = 100
    returns_data = np.random.normal(0.01, 0.05, (n_periods, n_assets))
    cov_matrix = np.cov(returns_data.T)
    print("   ✓ Data generated")
    
    # محاسبه بازده‌های فازی
    print("\n3. Computing fuzzy expected returns...")
    expected_returns_fuzzy = []
    for i in range(n_assets):
        fuzzy_ret = optimizer.fuzzy_expected_return(returns_data[:, i], 0.2)
        expected_returns_fuzzy.append(fuzzy_ret)
    print(f"   ✓ Computed {len(expected_returns_fuzzy)} fuzzy returns")
    
    # بهینه‌سازی پرتفوی
    print("\n4. Optimizing portfolio...")
    result = optimizer.optimize_fuzzy_portfolio(
        expected_returns_fuzzy,
        cov_matrix,
        max_weight=0.4,
        min_weight=0.05
    )
    
    assert 'weights' in result, "Optimization result missing weights"
    assert np.isclose(np.sum(result['weights']), 1.0), "Weights don't sum to 1"
    assert result['optimization_success'], "Optimization failed"
    print(f"   ✓ Portfolio optimized successfully")
    print(f"      Expected Return: {result['expected_return']:.2%}")
    print(f"      Risk: {result['risk']:.2%}")
    print(f"      Sharpe Ratio: {result['sharpe_ratio']:.3f}")
    
    # تست امکان‌سنجی
    print("\n5. Testing possibility maximization...")
    target = 0.01
    possibility = optimizer.possibility_maximization(
        result['weights'],
        expected_returns_fuzzy,
        target
    )
    assert 0 <= possibility <= 1, "Possibility out of range"
    print(f"   ✓ Possibility of achieving {target:.1%}: {possibility:.1%}")
    
    print("\n✅ Fuzzy Portfolio Module: ALL TESTS PASSED\n")
    return True


def test_rl_execution():
    """تست ماژول اجرای سفارش با RL"""
    print("=" * 60)
    print("Testing RL Optimal Execution Module")
    print("=" * 60)
    
    from ml_agents.rl_execution import MarketEnvironment, RLOptimalExecution
    
    # تست محیط بازار
    print("\n1. Testing Market Environment...")
    env = MarketEnvironment(
        initial_price=100.0,
        volatility=0.02,
        market_impact=0.001,
        transaction_cost=0.0005,
        max_steps=20
    )
    
    state = env.reset()
    assert len(state) == 5, "State dimension incorrect"
    assert env.remaining_quantity == 1.0, "Initial quantity should be 1.0"
    print("   ✓ Market environment initialized")
    
    # تست گام محیط
    print("\n2. Testing environment step...")
    action = 0.1
    next_state, reward, done, info = env.step(action)
    
    assert 'executed_qty' in info, "Info missing executed_qty"
    assert info['executed_qty'] > 0, "No quantity executed"
    assert env.remaining_quantity < 1.0, "Quantity not decreased"
    print(f"   ✓ Step executed: {info['executed_qty']:.2%} at ${info['execution_price']:.2f}")
    
    # تست عامل RL
    print("\n3. Testing RL Agent...")
    agent = RLOptimalExecution(
        algorithm='PPO',
        learning_rate=0.01,
        gamma=0.99
    )
    
    action = agent.select_action(state, explore=False)
    assert 0 <= action <= 1, "Action out of valid range"
    print(f"   ✓ Agent selected action: {action:.3f}")
    
    # آموزش کوتاه
    print("\n4. Testing training loop (short)...")
    env.reset()
    env.remaining_quantity = 1.0
    
    states, actions, rewards, next_states, dones = [], [], [], [], []
    for _ in range(10):
        action = agent.select_action(state, explore=True)
        next_state, reward, done, info = env.step(action)
        
        states.append(state)
        actions.append(action)
        rewards.append(reward)
        next_states.append(next_state)
        dones.append(done)
        
        state = next_state
        if done:
            break
    
    agent.update_policy(states, actions, rewards, next_states, dones)
    print(f"   ✓ Policy updated with {len(states)} samples")
    
    # تست استراتژی اجرا
    print("\n5. Testing execution strategy...")
    strategy = agent.get_execution_strategy({
        'price': 100.0,
        'volatility': 0.02
    })
    
    assert 'execution_plan' in strategy, "Strategy missing execution plan"
    assert strategy['total_executed'] > 0.9, "Low execution rate"
    print(f"   ✓ Execution strategy generated")
    print(f"      Total Executed: {strategy['total_executed']:.2%}")
    print(f"      Average Price: ${strategy['average_price']:.2f}")
    
    print("\n✅ RL Execution Module: ALL TESTS PASSED\n")
    return True


def run_all_tests():
    """اجرای تمام تست‌ها"""
    print("\n" + "=" * 60)
    print("QUANTUM-FUZZY FINANCE FRAMEWORK - COMPREHENSIVE TEST SUITE")
    print("=" * 60 + "\n")
    
    results = {}
    
    try:
        results['fuzzy_logic'] = test_fuzzy_logic()
    except Exception as e:
        print(f"\n❌ Fuzzy Logic Module: TEST FAILED - {str(e)}\n")
        results['fuzzy_logic'] = False
    
    try:
        results['fuzzy_portfolio'] = test_fuzzy_portfolio()
    except Exception as e:
        print(f"\n❌ Fuzzy Portfolio Module: TEST FAILED - {str(e)}\n")
        results['fuzzy_portfolio'] = False
    
    try:
        results['rl_execution'] = test_rl_execution()
    except Exception as e:
        print(f"\n❌ RL Execution Module: TEST FAILED - {str(e)}\n")
        results['rl_execution'] = False
    
    # خلاصه نتایج
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for module, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{module.replace('_', ' ').title()}: {status}")
    
    total_passed = sum(results.values())
    total_tests = len(results)
    
    print(f"\nOverall: {total_passed}/{total_tests} modules passed")
    
    if total_passed == total_tests:
        print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! 🎉\n")
        return True
    else:
        print(f"\n⚠️  {total_tests - total_passed} module(s) failed\n")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
