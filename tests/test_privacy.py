from privacy import mask_sensitive
def test_masks_pan_and_phone():
    result=mask_sensitive("PAN ABCDE1234F and phone 9876543210")
    assert "ABCDE1234F" not in result
    assert "9876543210" not in result
