"""
Comprehensive Test Suite for Quantum-Fuzzy Finance Framework

این فایل تست جامع برای تمام ماژول‌های پیاده‌سازی شده است
"""

import numpy as np
import sys
import os

# Add the quantum_fuzzy_finance package to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_fuzzy_logic():
    """تست ماژول منطق فازی"""
    print("=" * 60)
    print("Testing Fuzzy Logic Module")
    print("=" * 60)
    
    from quantum_fuzzy_finance.fuzzy_logic import (
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
    
    from quantum_fuzzy_finance.fuzzy_logic.fuzzy_portfolio import FuzzyPortfolioOptimizer
    
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
    
    from quantum_fuzzy_finance.ml_agents.rl_execution import MarketEnvironment, RLOptimalExecution
    
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


def test_network_analysis():
    """تست ماژول تحلیل شبکه"""
    print("=" * 60)
    print("Testing Network Analysis Module")
    print("=" * 60)
    
    # تست تحلیلگر شبکه مالی
    print("\n1. Testing Financial Network Analyzer...")
    analyzer = FinancialNetworkAnalyzer()
    
    # افزودن بانک‌ها
    analyzer.add_institution('bank_A', 'bank', total_assets=1000, capital_ratio=0.12)
    analyzer.add_institution('bank_B', 'bank', total_assets=800, capital_ratio=0.10)
    analyzer.add_institution('bank_C', 'bank', total_assets=500, capital_ratio=0.08)
    analyzer.add_institution('bank_D', 'bank', total_assets=300, capital_ratio=0.15)
    
    # افزودن مواجهه‌های بین بانکی
    analyzer.add_exposure('bank_A', 'bank_B', 100, 'interbank', 30)
    analyzer.add_exposure('bank_B', 'bank_C', 80, 'interbank', 45)
    analyzer.add_exposure('bank_C', 'bank_D', 50, 'interbank', 60)
    analyzer.add_exposure('bank_A', 'bank_D', 70, 'interbank', 30)
    
    # تست معیارهای مرکزیّت
    metrics = analyzer.calculate_centrality_metrics()
    assert len(metrics) == 4, "Should have metrics for all 4 banks"
    print("   ✓ Centrality metrics calculated")
    
    # تست شناسایی نهادهای سیستماتیک مهم
    sifis = analyzer.identify_systemically_important_institutions()
    assert isinstance(sifis, list), "SIFIs should be a list"
    print(f"   ✓ SIFIs identified: {len(sifis)} institutions")
    
    # تست شبیه‌سازی سرایت
    contagion_result = analyzer.simulate_contagion(['bank_A'], shock_magnitude=0.3)
    assert 'failed_institutions' in contagion_result, "Contagion result missing key"
    assert 'failure_rate' in contagion_result, "Failure rate missing"
    print(f"   ✓ Contagion simulation completed, failure rate: {contagion_result['failure_rate']:.2%}")
    
    # تست معیارهای ریسک شبکه
    risk_metrics = analyzer.calculate_network_risk_metrics()
    assert 0 <= risk_metrics.density <= 1, "Density should be in [0, 1]"
    assert risk_metrics.systemic_risk_score >= 0, "Systemic risk score should be non-negative"
    print(f"   ✓ Network risk metrics calculated, systemic score: {risk_metrics.systemic_risk_score:.4f}")
    
    # تست آنتروپی انتقال
    print("\n2. Testing Transfer Entropy Analyzer...")
    te_analyzer = TransferEntropyAnalyzer(k_history=3)
    
    # تولید داده‌های آزمایشی
    np.random.seed(42)
    n = 500
    leader = np.cumsum(np.random.randn(n))  # سری زمانی رهبر
    follower = np.cumsum(np.random.randn(n)) + 0.5 * leader[:-3]  # پیرو با تأخیر
    
    te = te_analyzer.calculate_transfer_entropy(leader[:len(follower)], follower)
    assert te >= 0, "Transfer entropy should be non-negative"
    print(f"   ✓ Transfer entropy calculated: {te:.6f}")
    
    # تست تشخیص رهبران و پیروان
    time_series = {
        'asset_A': leader[:len(follower)],
        'asset_B': follower
    }
    flow_result = te_analyzer.identify_leaders_and_followers(time_series, threshold=0.01)
    assert 'leaders' in flow_result, "Leaders key missing"
    assert 'followers' in flow_result, "Followers key missing"
    print(f"   ✓ Leaders/followers identified: {len(flow_result['leaders'])} leaders, {len(flow_result['followers'])} followers")
    
    # تست تحلیل توپولوژیک داده‌ها (TDA)
    print("\n3. Testing Topological Data Analyzer...")
    tda = TopologicalDataAnalyzer(max_dimension=2)
    
    # تولید نقاط تصادفی در فضای سه‌بعدی
    np.random.seed(42)
    points = np.random.randn(50, 3)
    
    persistence = tda.compute_persistence_diagram(points)
    assert isinstance(persistence, dict), "Persistence diagram should be a dict"
    print(f"   ✓ Persistence diagram computed with {len(persistence)} dimensions")
    
    # تست تشخیص تغییر رژیم
    np.random.seed(42)
    returns = np.random.randn(500) * 0.02  # بازده‌های روزانه
    regime_changes = tda.detect_regime_change(returns, window_size=50, threshold=0.3)
    assert isinstance(regime_changes, list), "Regime changes should be a list"
    print(f"   ✓ Regime change detection completed, {len(regime_changes)} changes detected")
    
    # تست تشخیص حباب
    np.random.seed(42)
    prices = 100 * np.cumprod(1 + np.random.randn(500) * 0.02)  # مسیر قیمت
    bubble_result = tda.bubble_detection(prices)
    assert 'is_bubble' in bubble_result, "Bubble result missing key"
    assert 'bubble_strength' in bubble_result, "Bubble strength missing"
    print(f"   ✓ Bubble detection completed, strength: {bubble_result['bubble_strength']:.4f}")
    
    print("\n✅ Network Analysis Module: ALL TESTS PASSED\n")
    return True


def test_engines():
    """تست موتورهای پیشرفته مالی"""
    print("=" * 60)
    print("Testing Advanced Financial Engines")
    print("=" * 60)
    
    # تست موتور مونت‌کارلو
    print("\n1. Testing Monte Carlo Engine...")
    mc = MonteCarloEngine(n_simulations=1000, random_seed=42)
    
    # شبیه‌سازی GBM
    paths = mc.simulate_gbm(S0=100, mu=0.10, sigma=0.20, T=1.0, n_steps=252)
    assert paths.shape[0] == 1000, "Should have 1000 simulations"
    assert paths.shape[1] == 253, "Should have 253 time steps (including initial)"
    assert paths[0, 0] == 100, "Initial price should be S0"
    print(f"   ✓ GBM simulation completed: {paths.shape[0]} paths, {paths.shape[1]} steps")
    
    # قیمت‌گذاری اختیار اروپایی
    option = mc.price_european_option(S0=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type='call')
    assert option.call_price > 0, "Call price should be positive"
    assert abs(option.call_delta - 0.5) < 0.2, "ATM call delta should be around 0.5"
    print(f"   ✓ European option priced: Call=${option.call_price:.4f}, Delta={option.call_delta:.4f}")
    
    # شبیه‌سازی چندمتغیره
    n_assets = 3
    S0_vec = np.array([100, 50, 75])
    mu_vec = np.array([0.10, 0.08, 0.12])
    cov_matrix = np.array([
        [0.04, 0.01, 0.005],
        [0.01, 0.09, 0.02],
        [0.005, 0.02, 0.06]
    ])
    
    multi_paths = mc.simulate_multivariate_gbm(S0_vec, mu_vec, cov_matrix, T=1.0, n_steps=252)
    assert multi_paths.shape == (1000, 253, 3), "Wrong shape for multivariate paths"
    print(f"   ✓ Multivariate GBM simulation completed: {multi_paths.shape}")
    
    # تولید سناریوهای استرس‌تست
    base_returns = np.array([0.08, 0.06, 0.10])
    base_cov = cov_matrix
    scenarios = mc.generate_stress_scenarios(base_returns, base_cov)
    assert 'market_crash' in scenarios, "Market crash scenario missing"
    assert 'volatility_spike' in scenarios, "Volatility spike scenario missing"
    print(f"   ✓ Stress scenarios generated: {list(scenarios.keys())}")
    
    # تست موتور ریسک
    print("\n2. Testing Risk Engine...")
    risk = RiskEngine(confidence_levels=[0.95, 0.99])
    
    # تولید بازده‌های تاریخی مصنوعی
    np.random.seed(42)
    n_days = 500
    returns_data = np.random.randn(n_days, 3) * 0.02 + np.array([0.0003, 0.0002, 0.0004])
    
    # VaR تاریخی
    var_hist = risk.calculate_var_historical(returns_data, horizon_days=1)
    assert 'var_95' in var_hist, "VaR 95% missing"
    assert 'var_99' in var_hist, "VaR 99% missing"
    assert var_hist['var_95'] > 0, "VaR should be positive"
    print(f"   ✓ Historical VaR calculated: 95%=${var_hist['var_95']:.4f}, 99%=${var_hist['var_99']:.4f}")
    
    # CVaR
    cvar = risk.calculate_cvar(returns_data)
    assert 'cvar_95' in cvar, "CVaR 95% missing"
    assert cvar['cvar_95'] >= var_hist['var_95'], "CVaR should be >= VaR"
    print(f"   ✓ CVaR calculated: 95%=${cvar['cvar_95']:.4f}")
    
    # معیارهای جامع ریسک
    weights = np.array([0.4, 0.3, 0.3])
    risk_metrics = risk.calculate_comprehensive_risk(returns_data, portfolio_weights=weights)
    assert risk_metrics.sharpe_ratio is not None, "Sharpe ratio missing"
    assert risk_metrics.max_drawdown >= 0, "Max drawdown should be non-negative"
    print(f"   ✓ Comprehensive risk metrics: Sharpe={risk_metrics.sharpe_ratio:.4f}, MaxDD={risk_metrics.max_drawdown:.2%}")
    
    # تست تولیدکننده داده‌های مصنوعی (Diffusion)
    print("\n3. Testing Diffusion Data Generator...")
    diffusion = DiffusionDataGenerator(noise_schedule='linear', n_timesteps=50)
    
    # داده اولیه
    np.random.seed(42)
    initial_data = np.random.randn(100, 10)  # 100 مسیر، 10 ویژگی
    
    # تولید داده مصنوعی
    synthetic = diffusion.generate_synthetic_paths(initial_data, n_paths=50, path_length=10)
    assert synthetic.shape[0] == 50, "Wrong number of synthetic paths"
    print(f"   ✓ Synthetic data generated: {synthetic.shape}")
    
    # افزایش داده
    augmented = diffusion.augment_training_data(initial_data, augmentation_factor=2)
    assert len(augmented) > len(initial_data), "Augmented data should be larger"
    print(f"   ✓ Data augmentation completed: {len(initial_data)} -> {len(augmented)} samples")
    
    print("\n✅ Advanced Financial Engines: ALL TESTS PASSED\n")
    return True


def run_all_tests():
    """اجرای تمام تست‌ها"""
    print("\n" + "=" * 60)
    print("QUANTUM-FUZZY FINANCE FRAMEWORK - COMPREHENSIVE TEST SUITE")
    print("Version 0.3.0 - Networks & Engines Edition")
    print("=" * 60 + "\n")
    
    results = {}
    
    try:
        results['fuzzy_logic'] = test_fuzzy_logic()
    except Exception as e:
        print(f"❌ Fuzzy Logic Module FAILED: {e}")
        results['fuzzy_logic'] = False
    
    try:
        results['fuzzy_portfolio'] = test_fuzzy_portfolio()
    except Exception as e:
        print(f"❌ Fuzzy Portfolio Module FAILED: {e}")
        results['fuzzy_portfolio'] = False
    
    try:
        results['rl_agents'] = test_rl_agents()
    except Exception as e:
        print(f"❌ RL Agents Module FAILED: {e}")
        results['rl_agents'] = False
        
    try:
        results['network_analysis'] = test_network_analysis()
    except Exception as e:
        print(f"❌ Network Analysis Module FAILED: {e}")
        results['network_analysis'] = False
        
    try:
        results['engines'] = test_engines()
    except Exception as e:
        print(f"❌ Engines Module FAILED: {e}")
        results['engines'] = False
    
    # خلاصه نتایج
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for module, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{module}: {status}")
    
    print(f"\nTotal: {passed}/{total} modules passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! 🎉\n")
        return True
    else:
        print(f"\n⚠️  {total - passed} module(s) failed\n")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
