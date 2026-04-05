import numpy as np
import pytest

from mujoco_mojo.utils.color import Color


def test_basic_color_constants():
    """Verify that fundamental colors convert to the correct normalized RGBA."""
    # Black: #000000 -> [0, 0, 0, 1]
    assert np.allclose(Color.BLACK.rgba, [0.0, 0.0, 0.0, 1.0])

    # White: #FFFFFF -> [1, 1, 1, 1]
    assert np.allclose(Color.WHITE.rgba, [1.0, 1.0, 1.0, 1.0])

    # Red 500: #EF4444
    # EF (239/255) ≈ 0.937, 44 (68/255) ≈ 0.266
    red_rgba = Color.RED_500.rgba
    assert red_rgba[0] > 0.9
    assert red_rgba[1] < 0.3
    assert red_rgba[3] == 1.0  # Default alpha


def test_hex_conversions():
    """Test the static hex utility methods."""
    # Test with and without '#'
    rgba1 = Color.hex_to_rgba("#FF0000")
    rgba2 = Color.hex_to_rgba("FF0000")
    assert np.array_equal(rgba1, rgba2)
    assert np.allclose(rgba1, [1.0, 0.0, 0.0, 1.0])

    # Test custom alpha
    rgba_alpha = Color.hex_to_rgba("00FF00", alpha=0.5)
    assert rgba_alpha[3] == 0.5

    # Test invalid hex
    with pytest.raises(ValueError, match="Invalid hex color"):
        Color.hex_to_rgba("ABC")


def test_rgba_to_hex_roundtrip():
    """Verify that converting to hex and back preserves the color."""
    original_hex = "#3b82f6"  # BLUE_500
    rgba = Color.hex_to_rgba(original_hex)

    # Alpha is discarded in hex_to_rgba, so we compare lowercase
    result_hex = Color.rgba_to_hex(rgba)
    assert result_hex.lower() == original_hex.lower()


def test_alpha_modifiers():
    """Test properties that modify transparency."""
    blue = Color.BLUE_500

    # Test with_alpha
    semi_transparent = blue.with_alpha(0.3)
    assert semi_transparent[3] == 0.3
    assert np.allclose(semi_transparent[:3], blue.rgb)

    # Test invisible
    ghost = blue.invisible
    assert ghost[3] == 0.0
    assert np.allclose(ghost[:3], blue.rgb)


def test_rgba255_conversions():
    """Test conversions between 0-255 and 0-1 ranges."""
    # [R255, G255, B255, Alpha1.0]
    color_255 = np.array([255.0, 127.5, 0.0, 1.0])

    # To normalized
    normalized = Color.rgba255_to_rgba(color_255)
    assert np.allclose(normalized, [1.0, 0.5, 0.0, 1.0])

    # Back to 255
    back_to_255 = Color.rgba_to_rgba255(normalized)
    assert np.allclose(back_to_255, color_255)


def test_random_rgba():
    """Ensure random colors are valid normalized RGBA vectors."""
    for _ in range(10):
        c = Color.random_rgba()
        assert isinstance(c, np.ndarray)
        assert len(c) == 4
        assert np.all((c >= 0) & (c <= 1))
        # Default random_rgba in your class appends 1 for alpha
        assert c[3] == 1.0


def test_rgb_property():
    """Verify the rgb property discards alpha."""
    rgba = Color.PURPLE_500.rgba
    rgb = Color.PURPLE_500.rgb

    assert len(rgb) == 3
    assert np.array_equal(rgb, rgba[:3])
