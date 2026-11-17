"""Smoke tests for the Streamlit app via streamlit.testing (offline: see conftest.no_network)."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _app():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


def _radio(at, label):
    return next(r for r in at.radio if r.label == label)


def _slider(at, prefix):
    return next(s for s in at.slider if s.label.startswith(prefix))


def _optimize(at):
    _slider(at, "Solver time limit").set_value(1)
    at.run()
    next(b for b in at.button if b.label == "Optimize routes").click()
    at.run()


def test_loads_sample_without_errors():
    at = _app()
    _radio(at, "Distance method").set_value("straight_line")
    at.run()
    assert not at.exception and not at.error
    assert at.metric[0].value == "45"


def test_optimize_sample_straight_line():
    at = _app()
    _radio(at, "Distance method").set_value("straight_line")
    _optimize(at)
    assert not at.exception and not at.error
    labels = {m.label: m.value for m in at.metric}
    assert int(labels["Riders"]) <= 23 and labels["Late orders"] == "0"
    next(s for s in at.selectbox if s.label == "Highlight rider").set_value(1)
    at.run()
    assert not at.exception and any("Rider 1" in m.value for m in at.markdown)


def test_default_promise_is_20():
    assert _slider(_app(), "Delivery promise").value == 20


def test_optimize_sample_osrm_from_cache():
    at = _app()  # default = road network; sample matrix comes from data/osrm_cache
    assert not any("can never be delivered" in w.value for w in at.warning)
    _optimize(at)
    assert not at.exception and not at.error
    assert any("Road network (OSRM)" in c.value for c in at.caption)


def test_infeasible_orders_can_be_excluded():
    at = _app()
    _slider(at, "Delivery promise").set_value(15)
    at.run()
    assert any("O05, O23" in w.value for w in at.warning)
    next(c for c in at.checkbox if c.label.startswith("Plan the remaining")).check()
    at.run()
    _optimize(at)
    assert not at.exception and not at.error
    assert any("Road network (OSRM)" in c.value for c in at.caption)


def test_osrm_failure_falls_back_with_warning():
    at = _app()
    at.radio[0].set_value("Generate new wave")
    at.run()
    _slider(at, "Number of orders").set_value(8)
    next(n for n in at.number_input if n.label == "Random seed").set_value(98765)
    at.run()  # coordinates never cached -> network disabled -> fallback
    assert any("unavailable" in w.value for w in at.warning)
    _optimize(at)
    assert not at.exception and not at.error
    assert any("Straight-line estimate" in c.value for c in at.caption)


def test_generate_small_wave_with_small_bag():
    at = _app()
    _radio(at, "Distance method").set_value("straight_line")
    at.radio[0].set_value("Generate new wave")
    at.run()
    _slider(at, "Number of orders").set_value(8)
    _slider(at, "Bag capacity").set_value(5)
    _optimize(at)
    assert not at.exception and not at.error
