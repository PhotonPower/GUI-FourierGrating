from fg_gui import system


def test_parse_nvidia_smi():
    out = "NVIDIA RTX 6000 Ada Generation, 1024, 49140, 3, 35, 570.86\n"
    rows = system.parse_nvidia_smi(out)
    assert rows[0]["GPU"] == "NVIDIA RTX 6000 Ada Generation" and rows[0]["Speicher gesamt [MiB]"] == "49140"
    assert system.parse_nvidia_smi("") == []
