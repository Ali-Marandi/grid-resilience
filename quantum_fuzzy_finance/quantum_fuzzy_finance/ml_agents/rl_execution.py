"""
Reinforcement Learning Module for Optimal Trade Execution

این ماژول از یادگیری تقویتی برای اجرای بهینه سفارشات استفاده می‌کند
تا هزینه‌های سایش (Slippage) را کاهش دهد.
الگوریتم‌های پشتیبانی‌شده: PPO, DDPG, SAC
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from abc import ABC, abstractmethod


class MarketEnvironment:
    """
    شبیه‌ساز محیط بازار برای آموزش عامل RL
    
    این کلاس یک بازار مصنوعی با ویژگی‌های زیر ایجاد می‌کند:
    - قیمت پایه با حرکت براونی هندسی
    - تاثیر سفارش بر قیمت (Market Impact)
    - هزینه‌های تراکنش
    - نوسانات تصادفی
    """
    
    def __init__(self, 
                 initial_price: float = 100.0,
                 volatility: float = 0.02,
                 market_impact: float = 0.001,
                 transaction_cost: float = 0.0005,
                 max_steps: int = 100):
        """
        Args:
            initial_price: قیمت اولیه دارایی
            volatility: نوسان‌پذیری روزانه
            market_impact: ضریب تاثیر سفارش بر قیمت
            transaction_cost: هزینه تراکنش
            max_steps: حداکثر گام‌های زمانی برای اجرا
        """
        self.initial_price = initial_price
        self.volatility = volatility
        self.market_impact = market_impact
        self.transaction_cost = transaction_cost
        self.max_steps = max_steps
        
        self.reset()
    
    def reset(self) -> np.ndarray:
        """بازنشانی محیط برای اپیزود جدید"""
        self.current_step = 0
        self.current_price = self.initial_price
        self.remaining_quantity = 1.0  # مقدار کل برای اجرا
        self.price_history = [self.initial_price]
        
        # تولید مسیر قیمت با GBM
        self.price_path = self._generate_price_path()
        
        return self._get_state()
    
    def _generate_price_path(self) -> np.ndarray:
        """تولید مسیر قیمت با حرکت براونی هندسی"""
        dt = 1.0 / 252  # گام زمانی روزانه
        returns = np.random.normal(0, self.volatility * np.sqrt(dt), self.max_steps)
        price_path = self.initial_price * np.cumprod(1 + returns)
        return price_path
    
    def _get_state(self) -> np.ndarray:
        """
        دریافت وضعیت فعلی محیط
        
        Returns:
            آرایه وضعیت شامل:
            - زمان باقی‌مانده
            - مقدار باقی‌مانده برای اجرا
            - قیمت فعلی
            - میانگین متحرک قیمت
            - نوسان اخیر
        """
        time_remaining = 1.0 - self.current_step / self.max_steps
        
        if len(self.price_history) >= 5:
            ma_price = np.mean(self.price_history[-5:])
            recent_vol = np.std(self.price_history[-5:])
        else:
            ma_price = self.current_price
            recent_vol = self.volatility
        
        state = np.array([
            time_remaining,
            self.remaining_quantity,
            self.current_price / self.initial_price,
            ma_price / self.initial_price,
            recent_vol / self.initial_price
        ])
        
        return state
    
    def step(self, action: float) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        اجرای یک اقدام در محیط
        
        Args:
            action: مقدار سفارش (کسر از کل مقدار باقی‌مانده)
            
        Returns:
            next_state: وضعیت بعدی
            reward: پاداش
            done: پایان اپیزود
            info: اطلاعات اضافی
        """
        # محدود کردن اقدام بین ۰ و ۱
        action = np.clip(action, 0.0, 1.0)
        
        # محاسبه مقدار اجرا شده
        executed_qty = action * self.remaining_quantity
        
        # قیمت اجرا با در نظر گرفتن تاثیر بازار
        impact = self.market_impact * executed_qty
        execution_price = self.current_price * (1 + impact)
        
        # هزینه تراکنش
        cost = executed_qty * execution_price * self.transaction_cost
        
        # محاسبه PnL لحظه‌ای
        pnl = executed_qty * (execution_price - self.initial_price) - cost
        
        # به‌روزرسانی وضعیت
        self.remaining_quantity -= executed_qty
        self.current_step += 1
        
        # حرکت به قیمت بعدی
        if self.current_step < len(self.price_path):
            self.current_price = self.price_path[self.current_step]
            self.price_history.append(self.current_price)
        
        # محاسبه پاداش (منفی کردن هزینه اجرا)
        reward = pnl / self.initial_price  # نرمال‌سازی
        
        # بررسی پایان اپیزود
        done = (self.current_step >= self.max_steps or 
                self.remaining_quantity < 0.01)
        
        info = {
            'executed_qty': executed_qty,
            'execution_price': execution_price,
            'pnl': pnl,
            'cost': cost,
            'remaining_qty': self.remaining_quantity
        }
        
        next_state = self._get_state()
        
        return next_state, reward, done, info


class RLOptimalExecution:
    """
    عامل یادگیری تقویتی برای اجرای بهینه سفارش
    
    پیاده‌سازی ساده‌شده از الگوریتم‌های PPO و DDPG
    """
    
    def __init__(self, 
                 algorithm: str = 'PPO',
                 learning_rate: float = 0.001,
                 gamma: float = 0.99,
                 state_dim: int = 5,
                 action_dim: int = 1):
        """
        Args:
            algorithm: الگوریتم RL ('PPO', 'DDPG')
            learning_rate: نرخ یادگیری
            gamma: ضریب تنزیل
            state_dim: بعد فضای وضعیت
            action_dim: بعد فضای اقدام
        """
        self.algorithm = algorithm
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # شبکه سیاست (Policy Network) - ساده‌شده
        self.weights = None
        self.bias = None
        
        self._initialize_network()
    
    def _initialize_network(self):
        """مقداردهی اولیه وزن‌های شبکه"""
        # شبکه خطی ساده برای نمایش سیاست
        self.weights = np.random.randn(self.state_dim, self.action_dim) * 0.1
        self.bias = np.zeros(self.action_dim)
    
    def select_action(self, state: np.ndarray, explore: bool = True) -> float:
        """
        انتخاب اقدام بر اساس سیاست فعلی
        
        Args:
            state: وضعیت فعلی
            explore: آیا کاوش انجام شود
            
        Returns:
            action: مقدار سفارش
        """
        # سیاست خطی ساده
        action_logits = state @ self.weights + self.bias
        
        if explore:
            # افزودن نویز گاوسی برای کاوش
            noise = np.random.randn(self.action_dim) * 0.1
            action = action_logits + noise
        else:
            action = action_logits
        
        # محدود کردن به بازه [0, 1] با sigmoid
        action = 1 / (1 + np.exp(-action))
        
        return action[0]
    
    def update_policy(self, 
                      states: List[np.ndarray],
                      actions: List[float],
                      rewards: List[float],
                      next_states: List[np.ndarray],
                      dones: List[bool]):
        """
        به‌روزرسانی سیاست با استفاده از الگوریتم Policy Gradient
        
        Args:
            states: لیست وضعیت‌ها
            actions: لیست اقدامات
            rewards: لیست پاداش‌ها
            next_states: لیست وضعیت‌های بعدی
            dones: لیست نشانگرهای پایان
        """
        # محاسبه مزیت‌ها (Advantage) با استفاده از TD Error
        advantages = []
        for i in range(len(rewards)):
            if i < len(rewards) - 1:
                next_value = np.mean(next_states[i] @ self.weights + self.bias)
                td_target = rewards[i] + self.gamma * next_value * (1 - dones[i])
            else:
                td_target = rewards[i]
            
            current_value = np.mean(states[i] @ self.weights + self.bias)
            advantage = td_target - current_value
            advantages.append(advantage)
        
        advantages = np.array(advantages).reshape(-1, 1)
        
        # به‌روزرسانی گرادیان سیاست
        states_matrix = np.array(states)
        actions_array = np.array(actions).reshape(-1, 1)
        
        # گرادیان
        gradient = states_matrix.T @ (advantages * (actions_array - 0.5)) / len(states)
        
        # به‌روزرسانی وزن‌ها
        self.weights += self.learning_rate * gradient
        self.bias += self.learning_rate * np.mean(advantages)
    
    def train(self, 
              env: MarketEnvironment,
              episodes: int = 1000,
              verbose: bool = True) -> Dict:
        """
        آموزش عامل RL
        
        Args:
            env: محیط بازار
            episodes: تعداد اپیزودهای آموزشی
            verbose: نمایش پیشرفت
            
        Returns:
            تاریخچه آموزش
        """
        training_history = {
            'episode_rewards': [],
            'avg_rewards': [],
            'total_executed': [],
            'avg_costs': []
        }
        
        for episode in range(episodes):
            state = env.reset()
            env.remaining_quantity = 1.0  # مقدار کل برای اجرا
            
            episode_reward = 0
            total_executed = 0
            total_cost = 0
            trajectory = []
            
            while True:
                # انتخاب اقدام
                action = self.select_action(state, explore=True)
                
                # اجرای اقدام در محیط
                next_state, reward, done, info = env.step(action)
                
                # ذخیره تجربه
                trajectory.append((state, action, reward, next_state, done))
                
                episode_reward += reward
                total_executed += info['executed_qty']
                total_cost += info['cost']
                
                state = next_state
                
                if done:
                    break
            
            # به‌روزرسانی سیاست با استفاده از تجربیات اپیزود
            states = [t[0] for t in trajectory]
            actions = [t[1] for t in trajectory]
            rewards = [t[2] for t in trajectory]
            next_states = [t[3] for t in trajectory]
            dones = [t[4] for t in trajectory]
            
            self.update_policy(states, actions, rewards, next_states, dones)
            
            # ذخیره تاریخچه
            training_history['episode_rewards'].append(episode_reward)
            training_history['total_executed'].append(total_executed)
            training_history['avg_costs'].append(total_cost / max(total_executed, 0.001))
            
            # میانگین متحرک پاداش‌ها
            if len(training_history['episode_rewards']) >= 10:
                avg_reward = np.mean(training_history['episode_rewards'][-10:])
            else:
                avg_reward = np.mean(training_history['episode_rewards'])
            
            training_history['avg_rewards'].append(avg_reward)
            
            if verbose and (episode + 1) % 100 == 0:
                print(f"Episode {episode + 1}/{episodes} | "
                      f"Avg Reward: {avg_reward:.4f} | "
                      f"Total Executed: {total_executed:.2%}")
        
        return training_history
    
    def get_execution_strategy(self, 
                               market_data: Dict) -> Dict:
        """
        دریافت استراتژی اجرایی بهینه پس از آموزش
        
        Args:
            market_data: داده‌های بازار شامل قیمت، نوسان، حجم
            
        Returns:
            دیکشنری استراتژی اجرا
        """
        # شبیه‌سازی اجرا با سیاست آموزش‌دیده
        env = MarketEnvironment(
            initial_price=market_data.get('price', 100.0),
            volatility=market_data.get('volatility', 0.02)
        )
        
        state = env.reset()
        env.remaining_quantity = 1.0
        
        execution_plan = []
        
        while True:
            action = self.select_action(state, explore=False)
            
            next_state, reward, done, info = env.step(action)
            
            execution_plan.append({
                'step': env.current_step,
                'quantity': info['executed_qty'],
                'price': info['execution_price'],
                'cumulative_qty': 1.0 - info['remaining_qty']
            })
            
            state = next_state
            
            if done:
                break
        
        return {
            'execution_plan': execution_plan,
            'total_executed': 1.0 - info['remaining_qty'],
            'average_price': np.mean([e['price'] for e in execution_plan]),
            'total_cost': sum([e['price'] * e['quantity'] * env.transaction_cost 
                              for e in execution_plan])
        }


# مثال استفاده
if __name__ == "__main__":
    print("=== RL Optimal Execution Example ===\n")
    
    # ایجاد محیط بازار
    env = MarketEnvironment(
        initial_price=100.0,
        volatility=0.02,
        market_impact=0.001,
        transaction_cost=0.0005,
        max_steps=50
    )
    
    # ایجاد و آموزش عامل RL
    agent = RLOptimalExecution(
        algorithm='PPO',
        learning_rate=0.01,
        gamma=0.99
    )
    
    print("Training RL agent for optimal execution...\n")
    
    history = agent.train(
        env,
        episodes=500,
        verbose=True
    )
    
    print("\n=== Training Complete ===")
    print(f"Final Avg Reward: {history['avg_rewards'][-1]:.4f}")
    print(f"Initial Avg Reward: {history['avg_rewards'][0]:.4f}")
    print(f"Improvement: {(history['avg_rewards'][-1] - history['avg_rewards'][0]) / abs(history['avg_rewards'][0]):.1%}")
    
    # تست استراتژی اجرا
    print("\n=== Execution Strategy Test ===")
    
    strategy = agent.get_execution_strategy({
        'price': 100.0,
        'volatility': 0.02
    })
    
    print(f"Total Executed: {strategy['total_executed']:.2%}")
    print(f"Average Price: ${strategy['average_price']:.2f}")
    print(f"Total Cost: ${strategy['total_cost']:.4f}")
    print(f"\nFirst 5 execution steps:")
    for step in strategy['execution_plan'][:5]:
        print(f"  Step {step['step']}: Qty={step['quantity']:.2%}, Price=${step['price']:.2f}")
