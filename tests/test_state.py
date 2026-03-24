"""Tests for rerun.engine.state — PlayerState model and state transitions."""

from rerun.engine.state import (
    PlayerState,
    create_player,
    get_btc_price,
    get_property_price,
)


class TestPlayerStateDefaults:
    def test_default_values(self):
        s = PlayerState()
        assert s.year == 2015
        assert s.savings == 80000.0
        assert s.btc_amount == 0.0
        assert s.stress == 20
        assert s.relationship == 50
        assert s.is_employed is True
        assert s.choices_log == []
        assert s.achievements == []

    def test_net_worth_no_assets(self):
        s = PlayerState()
        assert s.net_worth == 80000.0  # just savings

    def test_net_worth_with_btc(self):
        s = PlayerState(btc_amount=10.0, year=2017)
        # BTC price 2017 = 100,000
        assert s.btc_value == 1_000_000.0
        assert s.net_worth == 80000.0 + 1_000_000.0

    def test_net_worth_with_property(self):
        s = PlayerState(properties=2, year=2021)
        # Property price 2021 = 1,800,000
        assert s.property_value == 3_600_000.0

    def test_net_worth_combined(self):
        s = PlayerState(savings=100000, btc_amount=1.0, properties=1, stocks=50000, year=2025)
        expected = 100000 + 700000 + 1500000 + 50000
        assert s.net_worth == expected

    def test_annual_net_income_employed(self):
        s = PlayerState(monthly_salary=10000, monthly_expense=6000)
        # annual_net_income = salary*12 - annual_living_cost
        # In 2015: base living 36000 + rent 24000 = 60000
        assert s.annual_net_income == 10000 * 12 - s.annual_living_cost
        assert s.annual_living_cost == 60000  # base + rent in 2015

    def test_annual_net_income_unemployed(self):
        s = PlayerState(is_employed=False, monthly_expense=5000)
        # No salary, still pays living costs
        assert s.annual_net_income == -s.annual_living_cost


class TestApplyConsequences:
    def test_basic_delta(self):
        s = PlayerState(savings=80000)
        s2 = s.apply_consequences({"savings": -50000})
        assert s2.savings == 30000.0
        assert s.savings == 80000.0  # original unchanged

    def test_clamp_stress(self):
        s = PlayerState(stress=90)
        s2 = s.apply_consequences({"stress": 20})
        assert s2.stress == 100  # clamped at 100

        s3 = s.apply_consequences({"stress": -200})
        assert s3.stress == 0  # clamped at 0

    def test_clamp_btc_non_negative(self):
        s = PlayerState(btc_amount=5.0)
        s2 = s.apply_consequences({"btc_amount": -10.0})
        assert s2.btc_amount == 0.0

    def test_bool_replacement(self):
        s = PlayerState(has_partner=False)
        s2 = s.apply_consequences({"has_partner": True})
        assert s2.has_partner is True

    def test_str_replacement(self):
        s = PlayerState(job_title="普通上班族")
        s2 = s.apply_consequences({"job_title": "高级工程师"})
        assert s2.job_title == "高级工程师"

    def test_tracks_max_btc(self):
        s = PlayerState(btc_amount=0.0, max_btc_held=0.0)
        s2 = s.apply_consequences({"btc_amount": 10.0})
        assert s2.max_btc_held == 10.0

        s3 = s2.apply_consequences({"btc_amount": -5.0})
        assert s3.max_btc_held == 10.0  # still 10

    def test_tracks_sell_count(self):
        s = PlayerState(btc_amount=10.0, times_sold_btc=0)
        s2 = s.apply_consequences({"btc_amount": -3.0})
        assert s2.times_sold_btc == 1

    def test_ignores_unknown_keys(self):
        s = PlayerState()
        s2 = s.apply_consequences({"nonexistent_field": 999})
        assert s2 == s

    def test_multiple_consequences(self):
        s = PlayerState(savings=80000, stress=20, relationship=50)
        s2 = s.apply_consequences(
            {
                "savings": -30000,
                "stress": 15,
                "relationship": -10,
            }
        )
        assert s2.savings == 50000.0
        assert s2.stress == 35
        assert s2.relationship == 40


class TestRecordChoice:
    def test_appends_to_log(self):
        s = PlayerState()
        s2 = s.record_choice(2015, "Test Event", "A", "Do something", {"savings": -1000})
        assert len(s2.choices_log) == 1
        assert s2.choices_log[0]["year"] == 2015
        assert s2.choices_log[0]["choice_key"] == "A"
        assert len(s.choices_log) == 0  # original unchanged


class TestSettleYear:
    def test_advances_year_and_adds_income(self):
        s = PlayerState(year=2015, savings=80000, monthly_salary=8000, monthly_expense=5000)
        s2 = s.settle_year()
        assert s2.year == 2016
        # Uses detailed cost system: salary*12 - annual_living_cost
        assert s2.savings == 80000 + s.annual_net_income

    def test_unemployed_loses_money(self):
        s = PlayerState(year=2020, savings=100000, is_employed=False, monthly_expense=5000)
        s2 = s.settle_year()
        assert s2.year == 2021
        # No salary, pays full living costs
        assert s2.savings == 100000 - s.annual_living_cost
        assert s2.savings < 100000  # definitely lost money


class TestAchievements:
    def test_unlock(self):
        s = PlayerState()
        s2 = s.unlock_achievement("diamond_hands")
        assert "diamond_hands" in s2.achievements
        assert "diamond_hands" not in s.achievements

    def test_no_duplicate(self):
        s = PlayerState(achievements=["diamond_hands"])
        s2 = s.unlock_achievement("diamond_hands")
        assert s2.achievements.count("diamond_hands") == 1
        assert s2 is s  # same object, no change


class TestStartingPresets:
    def test_preset_1(self):
        p = create_player(1)
        assert p.savings == 30000.0
        assert p.job_title == "应届毕业生"

    def test_preset_2(self):
        p = create_player(2)
        assert p.savings == 80000.0

    def test_preset_3(self):
        p = create_player(3)
        assert p.savings == 200000.0
        assert p.has_partner is True

    def test_invalid_preset_defaults_to_2(self):
        p = create_player(99)
        assert p.savings == 80000.0


class TestPriceLookup:
    def test_btc_prices_exist(self):
        for year in range(2015, 2026):
            assert get_btc_price(year) > 0

    def test_property_prices_exist(self):
        for year in range(2015, 2026):
            assert get_property_price(year) > 0

    def test_unknown_year_returns_zero(self):
        assert get_btc_price(2000) == 0.0
        assert get_property_price(2000) == 0.0
