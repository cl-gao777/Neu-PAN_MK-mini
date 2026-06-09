from glob import glob
from setuptools import setup


package_name = "mkmini_neupan_bringup"

setup(
    name=package_name,
    version="0.1.0",
    packages=[],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="MK-mini NeuPAN Team",
    maintainer_email="maintainer@example.com",
    description="Bringup and configuration for NeuPAN navigation on the YUHESEN MK-mini.",
    license="Apache-2.0",
)
