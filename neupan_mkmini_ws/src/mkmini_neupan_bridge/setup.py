from glob import glob
from setuptools import find_packages, setup


package_name = "mkmini_neupan_bridge"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    tests_require=["pytest"],
    zip_safe=True,
    maintainer="MK-mini NeuPAN Team",
    maintainer_email="maintainer@example.com",
    description="Fail-safe Ackermann command bridge for NeuPAN and the YUHESEN MK-mini.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "ackermann_safety_bridge = mkmini_neupan_bridge.ackermann_safety_bridge_node:main",
            "legacy_neupan_twist_adapter = "
            "mkmini_neupan_bridge.legacy_neupan_twist_adapter_node:main",
        ],
    },
)
