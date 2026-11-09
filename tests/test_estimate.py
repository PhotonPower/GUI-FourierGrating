from fg_gui import estimate

CFG = {
    "dimension": "1D",
    "truncation": {"Nx": 15, "Nz": 0},
    "incidence": {"lambda_um": {"from": 0.5, "to": 0.7, "steps": 11}, "phi_deg": [0, 10, 20], "psi_deg": 0},
    "sweep": {"parameter": "/x", "values": [1, 2]},
}


def test_counts():
    assert estimate.scan_points(CFG) == 33
    assert estimate.sweep_values(CFG) == 2
    assert estimate.scan_points({}) == 1 and estimate.sweep_values({}) == 1


def test_matrix_size_1d_2d():
    assert estimate.fourier_terms(CFG) == 31 and estimate.matrix_size(CFG) == 124  # wie user_guide: 4 n_f = 124
    cfg2 = {"dimension": "2D", "truncation": {"Nx": 4, "Nz": 4}}
    assert estimate.matrix_size(cfg2) == 324  # 4 n_f = 324 (user_guide)


def test_memory_scales_with_parallel_points_and_n_squared():
    one = estimate.memory_bytes({"truncation": {"Nx": 10}}, cores=8)
    cfg = {"truncation": {"Nx": 10}, "incidence": {"lambda_um": [1, 2, 3]}}
    assert estimate.memory_bytes(cfg, cores=8) == 3 * one
    assert estimate.memory_bytes(cfg, cores=2) == 2 * one  # höchstens so viele parallel wie Kerne
    big = estimate.memory_bytes({"truncation": {"Nx": 20}}, cores=1)
    assert 3.5 < big / estimate.memory_bytes({"truncation": {"Nx": 10}}, cores=1) < 4.5


def test_format_and_summary():
    assert estimate.format_bytes(512) == "512 B" and estimate.format_bytes(2048) == "2.0 KiB"
    assert estimate.format_bytes(5 * 1024**3) == "5.0 GiB"
    s = estimate.summary(CFG, cores=4)
    assert s["scan_points"] == 33 and s["matrix_size"] == 124 and s["memory_text"].endswith("MiB")
