from sublimekeys.machine import get_or_create_machine_id


def test_machine_id_is_stable_across_calls(tmp_path):
    first = get_or_create_machine_id("test-product", base=tmp_path)
    second = get_or_create_machine_id("test-product", base=tmp_path)
    assert first == second


def test_machine_id_is_isolated_per_cache_dir(tmp_path):
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    id_a = get_or_create_machine_id("test-product", base=dir_a)
    id_b = get_or_create_machine_id("test-product", base=dir_b)
    assert id_a != id_b
