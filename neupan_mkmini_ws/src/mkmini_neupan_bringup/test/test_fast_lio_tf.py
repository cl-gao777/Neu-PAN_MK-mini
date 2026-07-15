import math
import unittest

from mkmini_neupan_bringup.fast_lio_tf import (
    inverse_transform,
    parse_fast_lio_tf,
)


class FastLioTfTest(unittest.TestCase):
    def test_uncalibrated_config_fails_when_required(self):
        config = {
            "calibrated": False,
            "frames": {
                "odom": "odom",
                "camera_init": "camera_init",
                "body": "body",
                "base": "base_link",
                "lidar": "livox_frame",
            },
            "base_to_livox": {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "roll": 0.0,
                "pitch": 0.0,
                "yaw": 0.0,
            },
        }

        with self.assertRaisesRegex(ValueError, "calibrated"):
            parse_fast_lio_tf(config, require_calibrated=True)

    def test_non_finite_calibration_is_rejected(self):
        config = {
            "calibrated": True,
            "frames": {
                "odom": "odom",
                "camera_init": "camera_init",
                "body": "body",
                "base": "base_link",
                "lidar": "livox_frame",
            },
            "base_to_livox": {
                "x": float("nan"),
                "y": 0.0,
                "z": 0.0,
                "roll": 0.0,
                "pitch": 0.0,
                "yaw": 0.0,
            },
        }

        with self.assertRaisesRegex(ValueError, "finite"):
            parse_fast_lio_tf(config)

    def test_inverse_transform_handles_translation_and_yaw(self):
        inverse = inverse_transform(
            translation=(1.0, 2.0, 3.0),
            rpy=(0.0, 0.0, math.pi / 2.0),
        )

        self.assertAlmostEqual(inverse.translation[0], -2.0)
        self.assertAlmostEqual(inverse.translation[1], 1.0)
        self.assertAlmostEqual(inverse.translation[2], -3.0)
        self.assertAlmostEqual(inverse.quaternion[0], 0.0)
        self.assertAlmostEqual(inverse.quaternion[1], 0.0)
        self.assertAlmostEqual(inverse.quaternion[2], -math.sqrt(0.5))
        self.assertAlmostEqual(inverse.quaternion[3], math.sqrt(0.5))


if __name__ == "__main__":
    unittest.main()
