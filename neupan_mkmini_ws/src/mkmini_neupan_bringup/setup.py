from glob import glob
from setuptools import find_packages, setup


package_name = "mkmini_neupan_bringup"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
        ("share/" + package_name + "/config", glob("config/*.json")),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/rviz", glob("rviz/*.rviz")),
    ],
    install_requires=["setuptools"],
    tests_require=["pytest"],
    zip_safe=True,
    maintainer="MK-mini NeuPAN Team",
    maintainer_email="maintainer@example.com",
    description="Bringup and configuration for NeuPAN navigation on the YUHESEN MK-mini.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "custom_msg_to_pointcloud2 = "
            "mkmini_neupan_bringup.custom_msg_to_pointcloud2_node:main",
            "thor_neupan_preflight = "
            "mkmini_neupan_bringup.thor_neupan_preflight_node:main",
        ],
    },
)
