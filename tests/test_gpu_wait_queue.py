from scripts.gpu_wait_queue import choose_gpu


def test_no_gpu_has_enough_memory():
    assert choose_gpu('0, 4096\n1, 8000\n', 8192) is None


def test_select_largest_available_including_exact_threshold():
    assert choose_gpu('0, 4096\n1, 8192\n2, 12000\n', 8192) == 2
    assert choose_gpu('3, 8192\n', 8192) == 3
