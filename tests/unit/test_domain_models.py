from yctm.domain.models import AcquisitionStatus


def test_acquisition_status_marks_terminal_states() -> None:
    assert AcquisitionStatus.STORED.is_terminal is True
    assert AcquisitionStatus.TERMINAL_ERROR.is_terminal is True
    assert AcquisitionStatus.PENDING.is_terminal is False
    assert AcquisitionStatus.RETRYABLE_ERROR.is_terminal is False
