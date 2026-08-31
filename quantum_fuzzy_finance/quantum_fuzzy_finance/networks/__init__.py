"""
شبکه‌های پیچیده و تحلیل سیستماتیک مالی
Network Analysis & Systemic Risk Modeling

این ماژول شامل ابزارهای پیشرفته برای:
- تحلیل شبکه‌های بانکی و سرایت ریسک
- شناسایی نهادهای "بزرگتر از آنکه شکست بخورند"
- گراف‌های همبستگی پویا
- آنتروپی انتقال و جریان اطلاعات
- تحلیل توپولوژیک داده‌ها (TDA)
"""

import numpy as np
import networkx as nx
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class NodeMetrics:
    """معیارهای مرکزیّت گره در شبکه"""
    degree_centrality: float
    betweenness_centrality: float
    closeness_centrality: float
    eigenvector_centrality: float
    pagerank: float
    is_systemically_important: bool


@dataclass
class NetworkRiskMetrics:
    """معیارهای ریسک شبکه"""
    density: float
    clustering_coefficient: float
    average_path_length: float
    assortativity: float
    largest_component_size: int
    systemic_risk_score: float
    contagion_threshold: float


class FinancialNetworkAnalyzer:
    """
    تحلیلگر شبکه‌های مالی پیچیده
    
    کاربردها:
    - مدل‌سازی شبکه بانک-شرکت
    - تحلیل سرایت شوک‌های مالی
    - شناسایی نهادهای سیستماتیک مهم
    - تشخیص زودهنگام بحران‌های مالی
    """
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.node_attributes = {}
        self.edge_weights = {}
        
    def add_institution(self, node_id: str, 
                       institution_type: str = 'bank',
                       total_assets: float = 1.0,
                       capital_ratio: float = 0.10,
                       **kwargs):
        """افزودن نهاد مالی به شبکه"""
        self.graph.add_node(node_id)
        self.node_attributes[node_id] = {
            'type': institution_type,
            'total_assets': total_assets,
            'capital_ratio': capital_ratio,
            **kwargs
        }
        
    def add_exposure(self, from_node: str, to_node: str, 
                    exposure_amount: float,
                    exposure_type: str = 'interbank',
                    maturity_days: int = 30):
        """افزودن مواجهه اعتباری بین نهادها"""
        self.graph.add_edge(from_node, to_node, 
                           weight=exposure_amount,
                           type=exposure_type,
                           maturity=maturity_days)
        self.edge_weights[(from_node, to_node)] = exposure_amount
        
    def build_bipartite_network(self, banks: List[str], 
                               assets: List[str],
                               holdings: Dict[Tuple[str, str], float]):
        """ساخت شبکه دوبخشی بانک-دارایی"""
        self.graph = nx.Graph()
        
        # افزودن گره‌های بانک‌ها
        for bank in banks:
            self.graph.add_node(f"bank_{bank}", bipartite=0, type='bank')
            
        # افزودن گره‌های دارایی‌ها
        for asset in assets:
            self.graph.add_node(f"asset_{asset}", bipartite=1, type='asset')
            
        # افزودن یال‌های مالکیت
        for (bank, asset), amount in holdings.items():
            self.graph.add_edge(f"bank_{bank}", f"asset_{asset}", 
                               weight=amount, type='holding')
                               
    def calculate_centrality_metrics(self, node_id: str = None) -> Dict:
        """محاسبه معیارهای مرکزیّت برای تمام گره‌ها"""
        if node_id:
            nodes = [node_id]
        else:
            nodes = list(self.graph.nodes())
            
        metrics = {}
        
        # محاسبه تمام معیارهای مرکزیّت
        degree_cent = nx.degree_centrality(self.graph)
        betweenness_cent = nx.betweenness_centrality(self.graph, weight='weight')
        closeness_cent = nx.closeness_centrality(self.graph, distance='weight')
        
        try:
            eigen_cent = nx.eigenvector_centrality_numpy(self.graph, weight='weight')
        except:
            eigen_cent = {n: 0.0 for n in self.graph.nodes()}
            
        try:
            pagerank = nx.pagerank(self.graph, weight='weight')
        except:
            pagerank = {n: 1.0/len(self.graph.nodes()) for n in self.graph.nodes()}
            
        for node in nodes:
            # تعیین آستانه اهمیت سیستماتیک
            is_important = (
                degree_cent.get(node, 0) > 0.5 or
                betweenness_cent.get(node, 0) > 0.3 or
                pagerank.get(node, 0) > 0.1
            )
            
            metrics[node] = NodeMetrics(
                degree_centrality=degree_cent.get(node, 0),
                betweenness_centrality=betweenness_cent.get(node, 0),
                closeness_centrality=closeness_cent.get(node, 0),
                eigenvector_centrality=eigen_cent.get(node, 0),
                pagerank=pagerank.get(node, 0),
                is_systemically_important=is_important
            )
            
        return metrics
        
    def identify_systemically_important_institutions(self) -> List[str]:
        """شناسایی نهادهای سیستماتیک مهم (SIFIs)"""
        metrics = self.calculate_centrality_metrics()
        sifis = [node for node, m in metrics.items() if m.is_systemically_important]
        return sifis
        
    def simulate_contagion(self, initial_shock_nodes: List[str],
                          shock_magnitude: float = 0.2,
                          max_iterations: int = 100) -> Dict:
        """
        شبیه‌سازی سرایت شوک در شبکه
        
        پارامترها:
        - initial_shock_nodes: لیست نهادهای اولیه تحت شوک
        - shock_magnitude: بزرگی شوک اولیه (درصد از دست دادن سرمایه)
        - max_iterations: حداکثر تکرار برای انتشار
        
        خروجی:
        - دیکشنری شامل نهادهای ورشکسته، تعداد تکرارها، و درصد کل شبکه متأثر
        """
        failed_institutions = set()
        current_shocks = {node: shock_magnitude for node in initial_shock_nodes}
        
        # کپی از سرمایه اولیه نهادها
        capital_buffers = {
            node: attr.get('capital_ratio', 0.10) * attr.get('total_assets', 1.0)
            for node, attr in self.node_attributes.items()
        }
        
        iteration = 0
        while current_shocks and iteration < max_iterations:
            next_shocks = {}
            
            for shocked_node, shock_size in current_shocks.items():
                if shocked_node in failed_institutions:
                    continue
                    
                # بررسی ورشکستگی
                if shock_size >= capital_buffers.get(shocked_node, 0):
                    failed_institutions.add(shocked_node)
                    
                    # انتشار شوک به همسایگان
                    for neighbor in self.graph.successors(shocked_node):
                        if neighbor not in failed_institutions:
                            edge_weight = self.graph[shocked_node][neighbor].get('weight', 1.0)
                            transmission_factor = min(1.0, edge_weight / 1000)  # نرمال‌سازی
                            transmitted_shock = shock_size * transmission_factor * 0.5
                            
                            if neighbor not in next_shocks:
                                next_shocks[neighbor] = 0
                            next_shocks[neighbor] += transmitted_shock
                            
            current_shocks = next_shocks
            iteration += 1
            
        return {
            'failed_institutions': list(failed_institutions),
            'total_failures': len(failed_institutions),
            'failure_rate': len(failed_institutions) / len(self.graph.nodes()) if self.graph.nodes() else 0,
            'iterations': iteration,
            'contagion_stopped': not current_shocks
        }
        
    def calculate_network_risk_metrics(self) -> NetworkRiskMetrics:
        """محاسبه معیارهای ریسک شبکه"""
        if len(self.graph.nodes()) == 0:
            return NetworkRiskMetrics(0, 0, 0, 0, 0, 0, 0)
            
        density = nx.density(self.graph)
        
        try:
            clustering = nx.average_clustering(self.graph.to_undirected())
        except:
            clustering = 0.0
            
        try:
            avg_path = nx.average_shortest_path_length(self.graph.to_undirected(), weight='weight')
        except:
            avg_path = float('inf')
            
        try:
            assortativity = nx.degree_assortativity_coefficient(self.graph)
        except:
            assortativity = 0.0
            
        # اندازه بزرگترین مؤلفه متصل
        if self.graph.is_directed():
            components = list(nx.weakly_connected_components(self.graph))
        else:
            components = list(nx.connected_components(self.graph))
        largest_component = max(len(c) for c in components) if components else 0
        
        # امتیاز ریسک سیستماتیک (ترکیبی از معیارها)
        systemic_score = (
            density * 0.3 +
            clustering * 0.2 +
            (1.0 / (1.0 + avg_path)) * 0.2 +
            abs(assortativity) * 0.15 +
            (largest_component / len(self.graph.nodes())) * 0.15
        )
        
        # آستانه سرایت (نقطه بحرانی)
        contagion_threshold = 1.0 / (density + 0.01)  # معکوس چگالی
        
        return NetworkRiskMetrics(
            density=density,
            clustering_coefficient=clustering,
            average_path_length=avg_path,
            assortativity=assortativity,
            largest_component_size=largest_component,
            systemic_risk_score=systemic_score,
            contagion_threshold=contagion_threshold
        )
        
    def detect_community_structure(self) -> List[Set[str]]:
        """تشخیص ساختار جامعه‌ای در شبکه"""
        try:
            communities = list(nx.community.louvain_communities(
                self.graph.to_undirected(), 
                weight='weight'
            ))
            return [set(comm) for comm in communities]
        except:
            return [set(self.graph.nodes())]
            
    def visualize_network_summary(self) -> str:
        """خلاصه متنی شبکه"""
        summary = []
        summary.append(f"تعداد نهادها: {len(self.graph.nodes())}")
        summary.append(f"تعداد مواجهه‌ها: {len(self.graph.edges())}")
        
        metrics = self.calculate_network_risk_metrics()
        summary.append(f"چگالی شبکه: {metrics.density:.4f}")
        summary.append(f"ضریب خوشه‌بندی: {metrics.clustering_coefficient:.4f}")
        summary.append(f"میانگین طول مسیر: {metrics.average_path_length:.2f}")
        summary.append(f"امتیاز ریسک سیستماتیک: {metrics.systemic_risk_score:.4f}")
        
        sifis = self.identify_systemically_important_institutions()
        summary.append(f"نهادهای سیستماتیک مهم: {len(sifis)}")
        if sifis:
            summary.append(f"  - {', '.join(sifis[:5])}{'...' if len(sifis) > 5 else ''}")
            
        return "\n".join(summary)


class TransferEntropyAnalyzer:
    """
    تحلیلگر آنتروپی انتقال برای سنجش جریان اطلاعات
    
    کاربردها:
    - تشخیص جهت علیت بین دارایی‌ها
    - شناسایی رهبران و پیروان بازار
    - اندازه‌گیری شدت انتقال شوک‌های اطلاعاتی
    """
    
    def __init__(self, k_history: int = 3):
        """
        پارامترها:
        - k_history: طول تاریخچه برای محاسبه آنتروپی شرطی
        """
        self.k = k_history
        
    def _calculate_entropy(self, series: np.ndarray) -> float:
        """محاسبه آنتروپی شانون"""
        # تبدیل به نمادین با استفاده از quantization
        n_bins = 10
        digitized = np.digitize(series, np.linspace(series.min(), series.max(), n_bins))
        
        # محاسبه توزیع احتمال
        unique, counts = np.unique(digitized, return_counts=True)
        probs = counts / len(digitized)
        
        # آنتروپی شانون
        entropy = -np.sum(probs * np.log2(probs + 1e-10))
        return entropy
        
    def _calculate_conditional_entropy(self, x: np.ndarray, y: np.ndarray) -> float:
        """محاسبه آنتروپی شرطی H(X|Y)"""
        n = len(x)
        joint_series = np.column_stack([x[self.k:], y[:-self.k]])
        
        # quantization چندمتغیره
        n_bins = 5
        joint_digitized = np.apply_along_axis(
            lambda col: np.digitize(col, np.linspace(col.min(), col.max(), n_bins)),
            0, joint_series
        )
        
        # تبدیل به tuple برای شمارش
        joint_tuples = [tuple(row) for row in joint_digitized]
        unique, counts = np.unique(joint_tuples, return_counts=True)
        joint_probs = counts / len(joint_tuples)
        
        joint_entropy = -np.sum(joint_probs * np.log2(joint_probs + 1e-10))
        
        # آنتروپی شرطی Y
        y_cond = y[:-self.k]
        y_entropy = self._calculate_entropy(y_cond)
        
        return joint_entropy - y_entropy
        
    def calculate_transfer_entropy(self, source: np.ndarray, 
                                  target: np.ndarray) -> float:
        """
        محاسبه آنتروپی انتقال از source به target
        
        TE(S→T) = H(T_future | T_past) - H(T_future | T_past, S_past)
        
        مقدار بالاتر نشان‌دهنده جریان اطلاعات قوی‌تر از source به target است
        """
        if len(source) != len(target) or len(source) <= self.k:
            return 0.0
            
        # آینده target
        t_future = target[self.k:]
        
        # گذشته target
        t_past = target[:-self.k]
        
        # گذشته source
        s_past = source[:-self.k]
        
        # H(T_future | T_past)
        h_t_future_given_t_past = self._calculate_conditional_entropy(t_future, t_past)
        
        # H(T_future | T_past, S_past)
        combined_past = np.column_stack([t_past, s_past])
        # Flatten properly by creating a combined index
        combined_index = combined_past[:, 0] * 10 + combined_past[:, 1]
        h_t_future_given_combined = self._calculate_conditional_entropy(t_future, combined_index)
        
        transfer_entropy = h_t_future_given_t_past - h_t_future_given_combined
        return max(0, transfer_entropy)  # آنتروپی انتقال نمی‌تواند منفی باشد
        
    def build_information_flow_matrix(self, 
                                     time_series_dict: Dict[str, np.ndarray]) -> np.ndarray:
        """ساخت ماتریس جریان اطلاعات بین تمام جفت دارایی‌ها"""
        assets = list(time_series_dict.keys())
        n_assets = len(assets)
        flow_matrix = np.zeros((n_assets, n_assets))
        
        for i, asset_i in enumerate(assets):
            for j, asset_j in enumerate(assets):
                if i != j:
                    te = self.calculate_transfer_entropy(
                        time_series_dict[asset_i],
                        time_series_dict[asset_j]
                    )
                    flow_matrix[i, j] = te
                    
        return flow_matrix
        
    def identify_leaders_and_followers(self,
                                      time_series_dict: Dict[str, np.ndarray],
                                      threshold: float = 0.1) -> Dict:
        """
        شناسایی دارایی‌های رهبر و پیرو بر اساس آنتروپی انتقال
        
        خروجی:
        - leaders: دارایی‌هایی که اطلاعات بیشتری صادر می‌کنند
        - followers: دارایی‌هایی که اطلاعات بیشتری دریافت می‌کنند
        - net_flow: خالص جریان اطلاعات برای هر دارایی
        """
        flow_matrix = self.build_information_flow_matrix(time_series_dict)
        assets = list(time_series_dict.keys())
        
        out_flow = np.sum(flow_matrix, axis=1)  # اطلاعات ارسالی
        in_flow = np.sum(flow_matrix, axis=0)   # اطلاعات دریافتی
        net_flow = out_flow - in_flow
        
        leaders = [assets[i] for i in range(len(assets)) if net_flow[i] > threshold]
        followers = [assets[i] for i in range(len(assets)) if net_flow[i] < -threshold]
        
        return {
            'leaders': leaders,
            'followers': followers,
            'net_flow': dict(zip(assets, net_flow)),
            'flow_matrix': flow_matrix
        }


class TopologicalDataAnalyzer:
    """
    تحلیل توپولوژیک داده‌ها (TDA) برای تشخیص تغییر رژیم بازار
    
    کاربردها:
    - شناسایی حباب‌های مالی پیش از وقوع
    - تشخیص تغییر رژیم بازار
    - کشف ساختارهای پنهان در داده‌های با ابعاد بالا
    - Persistent Homology برای تحلیل پایداری ویژگی‌های توپولوژیک
    """
    
    def __init__(self, max_dimension: int = 2):
        """
        پارامترها:
        - max_dimension: حداکثر بعد همولوژی برای تحلیل
        """
        self.max_dim = max_dimension
        
    def _build_vietoris_rips_complex(self, points: np.ndarray, 
                                    epsilon: float) -> List[Set[int]]:
        """ساخت کمپلکس Vietoris-Rips"""
        n_points = len(points)
        simplices = []
        
        # 0-simplices (رأس‌ها)
        for i in range(n_points):
            simplices.append({i})
            
        # 1-simplices (یال‌ها)
        edges = []
        for i in range(n_points):
            for j in range(i+1, n_points):
                dist = np.linalg.norm(points[i] - points[j])
                if dist <= epsilon:
                    edges.append({i, j})
        simplices.extend(edges)
        
        # higher-order simplices (مثلث‌ها، تتراهدرا و ...)
        # برای سادگی، فقط تا 2-simplices را محاسبه می‌کنیم
        if self.max_dim >= 2:
            for i in range(len(edges)):
                for j in range(i+1, len(edges)):
                    edge_i = edges[i]
                    edge_j = edges[j]
                    
                    # بررسی اشتراک دو رأس
                    shared = edge_i.intersection(edge_j)
                    if len(shared) == 1:
                        triangle = edge_i.union(edge_j)
                        if len(triangle) == 3:
                            # بررسی اینکه همه یال‌ها وجود دارند
                            triangle_list = list(triangle)
                            all_edges_exist = True
                            for a in range(3):
                                for b in range(a+1, 3):
                                    edge_ab = {triangle_list[a], triangle_list[b]}
                                    if edge_ab not in edges:
                                        all_edges_exist = False
                                        break
                                if not all_edges_exist:
                                    break
                                    
                            if all_edges_exist:
                                simplices.append(triangle)
                                
        return simplices
        
    def _compute_betti_numbers(self, simplices: List[Set[int]]) -> Dict[int, int]:
        """محاسبه اعداد بتی (تعداد حفره‌های توپولوژیک)"""
        betti = {0: 0, 1: 0, 2: 0}
        
        # شمارش ساده بر اساس نوع سیمپلکس
        vertices = [s for s in simplices if len(s) == 1]
        edges = [s for s in simplices if len(s) == 2]
        triangles = [s for s in simplices if len(s) == 3]
        
        # عدد بتی 0: تعداد مؤلفه‌های متصل
        # عدد بتی 1: تعداد حلقه‌ها
        # عدد بتی 2: تعداد حفره‌های سه‌بعدی
        
        # تقریب ساده
        betti[0] = max(1, len(vertices) - len(edges) + len(triangles))
        betti[1] = max(0, len(edges) - len(vertices) - len(triangles) // 2)
        betti[2] = max(0, len(triangles) // 4)
        
        return betti
        
    def compute_persistence_diagram(self, points: np.ndarray,
                                   epsilon_range: Tuple[float, float, float] = (0.1, 2.0, 0.1)) -> Dict:
        """
        محاسبه نمودار پایداری (Persistence Diagram)
        
        پارامترها:
        - points: نقاط داده در فضای با ابعاد بالا
        - epsilon_range: (start, end, step) برای فیلتراسیون
        
        خروجی:
        - دیکشنری شامل اعداد بتی در مقیاس‌های مختلف
        """
        eps_start, eps_end, eps_step = epsilon_range
        persistence = defaultdict(list)
        
        epsilons = np.arange(eps_start, eps_end, eps_step)
        
        for eps in epsilons:
            simplices = self._build_vietoris_rips_complex(points, eps)
            betti = self._compute_betti_numbers(simplices)
            
            for dim in range(self.max_dim + 1):
                persistence[dim].append((eps, betti[dim]))
                
        return dict(persistence)
        
    def detect_regime_change(self, returns_data: np.ndarray,
                            window_size: int = 60,
                            threshold: float = 0.5) -> List[int]:
        """
        تشخیص تغییر رژیم بازار با استفاده از TDA
        
        پارامترها:
        - returns_data: آرایه بازده‌های زمانی
        - window_size: اندازه پنجره غلتان
        - threshold: آستانه برای تشخیص تغییر ناگهانی
        
        خروجی:
        - لیست ایندکس‌هایی که تغییر رژیم رخ داده است
        """
        n = len(returns_data)
        regime_changes = []
        
        if n < window_size * 2:
            return regime_changes
            
        # ایجاد embedding تأخیری برای ساخت فضای حالت
        delay = 5
        embedded_points = []
        
        for i in range(n - delay * 10):
            point = np.array([returns_data[i + j * delay] for j in range(10)])
            embedded_points.append(point)
            
        embedded_points = np.array(embedded_points)
        
        # محاسبه اعداد بتی در پنجره‌های غلتان
        prev_betti_sum = None
        
        for start_idx in range(0, len(embedded_points) - window_size, window_size // 2):
            window_points = embedded_points[start_idx:start_idx + window_size]
            
            if len(window_points) < 10:
                continue
                
            # محاسبه persistence diagram
            persistence = self.compute_persistence_diagram(window_points)
            
            # جمع اعداد بتی به عنوان خلاصه توپولوژیک
            betti_sum = sum(sum(v for _, v in persistence.get(dim, [])) 
                           for dim in range(self.max_dim + 1))
            
            if prev_betti_sum is not None:
                change_magnitude = abs(betti_sum - prev_betti_sum) / (prev_betti_sum + 1e-10)
                
                if change_magnitude > threshold:
                    regime_changes.append(start_idx + window_size // 2)
                    
            prev_betti_sum = betti_sum
            
        return regime_changes
        
    def bubble_detection(self, price_data: np.ndarray,
                        volume_data: np.ndarray = None) -> Dict:
        """
        تشخیص حباب‌های مالی با استفاده از TDA
        
        پارامترها:
        - price_data: سری زمانی قیمت‌ها
        - volume_data: سری زمانی حجم معاملات (اختیاری)
        
        خروجی:
        - دیکشنری شامل سیگنال‌های حباب، قدرت حباب، و زمان‌های بحرانی
        """
        # محاسبه بازده‌ها
        returns = np.diff(price_data) / price_data[:-1]
        
        # اگر حجم موجود است، فضای حالت چندبعدی بسازید
        if volume_data is not None:
            volume_returns = np.diff(volume_data) / volume_data[:-1]
            min_len = min(len(returns), len(volume_returns))
            points = np.column_stack([returns[:min_len], volume_returns[:min_len]])
        else:
            # embedding تأخیری یک‌بعدی
            delay = 3
            points = np.array([
                [returns[i], returns[i-delay] if i >= delay else 0, 
                 returns[i-2*delay] if i >= 2*delay else 0]
                for i in range(len(returns))
            ])
            
        # تشخیص تغییر رژیم
        regime_changes = self.detect_regime_change(returns)
        
        # محاسبه پایداری توپولوژیک
        persistence = self.compute_persistence_diagram(points)
        
        # معیار حباب: افزایش ناگهانی در اعداد بتی 1 (حلقه‌ها)
        betti_1_values = [v for _, v in persistence.get(1, [])]
        if len(betti_1_values) > 5:
            betti_1_mean = np.mean(betti_1_values[:-5])  # میانگین تاریخی
            recent_betti_1 = np.mean(betti_1_values[-5:])  # میانگین اخیر
            
            bubble_strength = (recent_betti_1 - betti_1_mean) / (betti_1_mean + 1e-10)
            is_bubble = bubble_strength > 1.5  # آستانه
        else:
            bubble_strength = 0.0
            is_bubble = False
            
        return {
            'is_bubble': is_bubble,
            'bubble_strength': bubble_strength,
            'regime_change_points': regime_changes,
            'topological_summary': persistence,
            'warning_signal': len(regime_changes) > 0 or is_bubble
        }


__all__ = [
    'FinancialNetworkAnalyzer',
    'TransferEntropyAnalyzer', 
    'TopologicalDataAnalyzer',
    'NodeMetrics',
    'NetworkRiskMetrics'
]
