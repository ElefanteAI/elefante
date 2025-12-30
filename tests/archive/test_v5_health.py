"""
V5 Property Tests: Memory Health Score (Req-2) + Conflict Detection (Req-3)

Properties:
- P3: Health status exhaustiveness (exactly 4 states, priority order)
- P4: Health computation determinism (same inputs → same output)
- P5: Conflict detection symmetry (conflict(a,b) == conflict(b,a))
- P6: Conflict threshold monotonicity (higher threshold → fewer conflicts)
"""
import pytest
from hypothesis import given, strategies as st, settings, assume

from src.utils.curation import (
    HealthStatus,
    HealthReport,
    ConflictReport,
    MemoryHealthAnalyzer,
)


# ============================================================================
# PROPERTY 3: Health Status Exhaustiveness
# ============================================================================

class TestP3Exhaustiveness:
    """Every memory gets exactly one of 4 health statuses."""
    
    def test_enum_has_exactly_four_states(self):
        """HealthStatus enum covers all states."""
        states = list(HealthStatus)
        assert len(states) == 4
        assert HealthStatus.HEALTHY in states
        assert HealthStatus.STALE in states
        assert HealthStatus.AT_RISK in states
        assert HealthStatus.ORPHAN in states
    
    @given(
        superseded=st.booleans(),
        has_conflicts=st.booleans(),
        days_since_access=st.integers(0, 1000),
        connection_count=st.integers(0, 100),
    )
    @settings(max_examples=200)
    def test_always_returns_valid_status(
        self, superseded, has_conflicts, days_since_access, connection_count
    ):
        """Any input combination returns exactly one valid status."""
        analyzer = MemoryHealthAnalyzer()
        
        report = analyzer.compute_health(
            superseded_by_id="some-id" if superseded else None,
            potential_conflicts=["c1", "c2"] if has_conflicts else None,
            days_since_access=days_since_access,
            connection_count=connection_count,
        )
        
        # Returns HealthReport
        assert isinstance(report, HealthReport)
        
        # Status is valid enum member
        assert report.status in HealthStatus
        
        # Has icon (non-empty)
        assert report.icon
        
        # Has at least one reason
        assert len(report.reasons) >= 1
    
    def test_priority_order_superseded_first(self):
        """Superseded takes priority over all other conditions."""
        analyzer = MemoryHealthAnalyzer()
        
        # Superseded + stale + orphan → AT_RISK (not stale/orphan)
        report = analyzer.compute_health(
            superseded_by_id="newer-id",
            potential_conflicts=None,
            days_since_access=500,  # Would be stale
            connection_count=0,     # Would be orphan
        )
        assert report.status == HealthStatus.AT_RISK
        assert "Superseded" in report.reasons[0]
    
    def test_priority_order_conflicts_second(self):
        """Conflicts take priority over stale/orphan."""
        analyzer = MemoryHealthAnalyzer()
        
        # Conflicts + stale + orphan → AT_RISK
        report = analyzer.compute_health(
            superseded_by_id=None,
            potential_conflicts=["conflict-1"],
            days_since_access=500,  # Would be stale
            connection_count=0,     # Would be orphan
        )
        assert report.status == HealthStatus.AT_RISK
        assert "conflict" in report.reasons[0].lower()
    
    def test_priority_order_stale_third(self):
        """Stale takes priority over orphan."""
        analyzer = MemoryHealthAnalyzer()
        
        # Stale + orphan → STALE
        report = analyzer.compute_health(
            superseded_by_id=None,
            potential_conflicts=None,
            days_since_access=200,  # Stale
            connection_count=0,     # Would be orphan
        )
        assert report.status == HealthStatus.STALE
        assert "200 days" in report.reasons[0]
    
    def test_priority_order_orphan_fourth(self):
        """Orphan only if nothing else applies."""
        analyzer = MemoryHealthAnalyzer()
        
        # Only orphan
        report = analyzer.compute_health(
            superseded_by_id=None,
            potential_conflicts=None,
            days_since_access=30,   # Not stale
            connection_count=0,     # Orphan
        )
        assert report.status == HealthStatus.ORPHAN
    
    def test_healthy_is_default(self):
        """Healthy when all conditions are good."""
        analyzer = MemoryHealthAnalyzer()
        
        report = analyzer.compute_health(
            superseded_by_id=None,
            potential_conflicts=None,
            days_since_access=30,
            connection_count=5,
        )
        assert report.status == HealthStatus.HEALTHY


# ============================================================================
# PROPERTY 4: Health Computation Determinism
# ============================================================================

class TestP4Determinism:
    """Same inputs always produce the same health status."""
    
    @given(
        superseded=st.booleans(),
        has_conflicts=st.booleans(),
        days=st.integers(0, 500),
        connections=st.integers(0, 50),
    )
    @settings(max_examples=200)
    def test_same_inputs_same_output(
        self, superseded, has_conflicts, days, connections
    ):
        """Repeated calls with identical inputs return identical results."""
        analyzer = MemoryHealthAnalyzer()
        
        kwargs = dict(
            superseded_by_id="x" if superseded else None,
            potential_conflicts=["y"] if has_conflicts else None,
            days_since_access=days,
            connection_count=connections,
        )
        
        report1 = analyzer.compute_health(**kwargs)
        report2 = analyzer.compute_health(**kwargs)
        
        assert report1.status == report2.status
        assert report1.icon == report2.icon
        assert report1.reasons == report2.reasons
    
    @given(stale_days=st.integers(1, 365))
    @settings(max_examples=50)
    def test_configurable_stale_threshold(self, stale_days):
        """Custom stale_days threshold respected."""
        analyzer = MemoryHealthAnalyzer(stale_days=stale_days)
        
        # Just below threshold → healthy
        report_below = analyzer.compute_health(
            days_since_access=stale_days - 1,
            connection_count=1,
        )
        
        # Just above threshold → stale
        report_above = analyzer.compute_health(
            days_since_access=stale_days + 1,
            connection_count=1,
        )
        
        assert report_below.status == HealthStatus.HEALTHY
        assert report_above.status == HealthStatus.STALE


# ============================================================================
# PROPERTY 5: Conflict Detection Symmetry
# ============================================================================

class TestP5ConflictSymmetry:
    """Conflict detection is symmetric: conflict(a,b) iff conflict(b,a)."""
    
    @given(
        concepts_a=st.lists(st.sampled_from(["python", "react", "testing", "api", "db"]), min_size=1, max_size=5),
        concepts_b=st.lists(st.sampled_from(["python", "react", "testing", "api", "db"]), min_size=1, max_size=5),
        domain=st.sampled_from(["work", "personal", "learning"]),
    )
    @settings(max_examples=150)
    def test_symmetry(self, concepts_a, concepts_b, domain):
        """conflict(a,b) exists iff conflict(b,a) exists."""
        analyzer = MemoryHealthAnalyzer()
        
        conflict_ab = analyzer.detect_potential_conflict(
            memory_a_id="mem-a",
            memory_a_concepts=concepts_a,
            memory_a_domain=domain,
            memory_b_id="mem-b",
            memory_b_concepts=concepts_b,
            memory_b_domain=domain,
        )
        
        conflict_ba = analyzer.detect_potential_conflict(
            memory_a_id="mem-b",
            memory_a_concepts=concepts_b,
            memory_a_domain=domain,
            memory_b_id="mem-a",
            memory_b_concepts=concepts_a,
            memory_b_domain=domain,
        )
        
        # Both exist or neither exists
        assert (conflict_ab is None) == (conflict_ba is None)
        
        # If both exist, same overlap
        if conflict_ab and conflict_ba:
            assert conflict_ab.overlap == conflict_ba.overlap
    
    def test_different_domains_no_conflict(self):
        """Different domains never conflict."""
        analyzer = MemoryHealthAnalyzer()
        
        # 100% overlap but different domains
        conflict = analyzer.detect_potential_conflict(
            memory_a_id="mem-a",
            memory_a_concepts=["python", "testing"],
            memory_a_domain="work",
            memory_b_id="mem-b",
            memory_b_concepts=["python", "testing"],
            memory_b_domain="personal",
        )
        
        assert conflict is None


# ============================================================================
# PROPERTY 6: Conflict Threshold Monotonicity
# ============================================================================

class TestP6ThresholdMonotonicity:
    """Higher conflict threshold → fewer or equal conflicts detected."""
    
    @given(
        threshold_low=st.floats(0.1, 0.5),
        threshold_high=st.floats(0.6, 0.95),
    )
    @settings(max_examples=100)
    def test_higher_threshold_fewer_conflicts(self, threshold_low, threshold_high):
        """Strict threshold detects <= conflicts than lenient threshold."""
        assume(threshold_low < threshold_high)
        
        analyzer_lenient = MemoryHealthAnalyzer(conflict_threshold=threshold_low)
        analyzer_strict = MemoryHealthAnalyzer(conflict_threshold=threshold_high)
        
        # Test data: moderate overlap
        concepts_a = ["python", "testing", "api"]
        concepts_b = ["python", "testing", "db"]
        
        conflict_lenient = analyzer_lenient.detect_potential_conflict(
            memory_a_id="a", memory_a_concepts=concepts_a, memory_a_domain="work",
            memory_b_id="b", memory_b_concepts=concepts_b, memory_b_domain="work",
        )
        
        conflict_strict = analyzer_strict.detect_potential_conflict(
            memory_a_id="a", memory_a_concepts=concepts_a, memory_a_domain="work",
            memory_b_id="b", memory_b_concepts=concepts_b, memory_b_domain="work",
        )
        
        # If strict finds conflict, lenient must also find it
        if conflict_strict is not None:
            assert conflict_lenient is not None


# ============================================================================
# BATCH ANALYSIS TESTS
# ============================================================================

class TestBatchAnalysis:
    """Test analyze_all() method."""
    
    def test_analyze_all_returns_all_health(self):
        """Every memory gets a health report."""
        analyzer = MemoryHealthAnalyzer()
        
        memories = [
            {"id": "m1", "concepts": ["a"], "domain": "work", "days_since_access": 10, "connection_count": 3},
            {"id": "m2", "concepts": ["a"], "domain": "work", "days_since_access": 200, "connection_count": 1},
            {"id": "m3", "concepts": ["b"], "domain": "personal", "days_since_access": 5, "connection_count": 0},
        ]
        
        health_map, conflicts = analyzer.analyze_all(memories)
        
        assert len(health_map) == 3
        assert "m1" in health_map
        assert "m2" in health_map
        assert "m3" in health_map
        
        assert health_map["m1"].status == HealthStatus.HEALTHY
        assert health_map["m2"].status == HealthStatus.STALE
        assert health_map["m3"].status == HealthStatus.ORPHAN
    
    def test_analyze_all_finds_conflicts(self):
        """Batch analysis detects pairwise conflicts."""
        analyzer = MemoryHealthAnalyzer(conflict_threshold=0.5)
        
        memories = [
            {"id": "m1", "concepts": ["python", "testing"], "domain": "work", "days_since_access": 10, "connection_count": 1},
            {"id": "m2", "concepts": ["python", "testing"], "domain": "work", "days_since_access": 10, "connection_count": 1},
            {"id": "m3", "concepts": ["react", "ui"], "domain": "work", "days_since_access": 10, "connection_count": 1},
        ]
        
        health_map, conflicts = analyzer.analyze_all(memories)
        
        # m1 and m2 have 100% overlap → conflict
        # m3 is different → no conflict with m1/m2
        assert len(conflicts) == 1
        assert conflicts[0].overlap == 1.0
        assert set([conflicts[0].memory_a_id, conflicts[0].memory_b_id]) == {"m1", "m2"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
