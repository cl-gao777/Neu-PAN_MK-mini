import argparse
import importlib
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence


CHECKPOINT_PLACEHOLDER = "REPLACE_WITH_TRAINED_MKMINI_DUNE_CHECKPOINT"
REQUIRED_MODULES = ("torch", "cvxpy", "cvxpylayers", "neupan")


@dataclass(frozen=True)
class TopicRateCheck:
    topic: str
    min_rate_hz: float
    timeout_sec: float


REQUIRED_TOPIC_RATES = (
    TopicRateCheck("/livox/lidar", 8.0, 8.0),
    TopicRateCheck("/livox/points", 8.0, 8.0),
    TopicRateCheck("/odom", 5.0, 8.0),
    TopicRateCheck("/scan", 5.0, 8.0),
    TopicRateCheck("/plan", 0.1, 20.0),
    TopicRateCheck("/chassis_info_fb", 5.0, 8.0),
    TopicRateCheck("/veh_diag_fb", 2.0, 8.0),
    TopicRateCheck("/ctrl_cmd", 10.0, 8.0),
)


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str

    @property
    def failed(self) -> bool:
        return self.status == "FAIL"


@dataclass
class CommandResult:
    args: Sequence[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


Runner = Callable[[Sequence[str], float], CommandResult]


def run_command(args: Sequence[str], timeout_sec: float) -> CommandResult:
    try:
        completed = subprocess.run(
            list(args),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except FileNotFoundError as error:
        return CommandResult(args, 127, stderr=str(error))
    except subprocess.TimeoutExpired as error:
        stdout = _coerce_output(error.stdout)
        stderr = _coerce_output(error.stderr)
        return CommandResult(args, 124, stdout=stdout, stderr=stderr, timed_out=True)
    return CommandResult(args, completed.returncode, completed.stdout, completed.stderr)


def _coerce_output(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def check_python_modules(
    importer: Callable[[str], object] = importlib.import_module,
) -> list[CheckResult]:
    results = []
    for module_name in REQUIRED_MODULES:
        try:
            module = importer(module_name)
        except Exception as error:
            results.append(
                CheckResult(
                    f"Python module {module_name}",
                    "FAIL",
                    str(error),
                )
            )
            continue
        version = getattr(module, "__version__", "unknown")
        results.append(
            CheckResult(
                f"Python module {module_name}",
                "PASS",
                f"version {version}",
            )
        )
    return results


def default_neupan_config_path() -> Path:
    try:
        from ament_index_python.packages import get_package_share_directory

        return (
            Path(get_package_share_directory("mkmini_neupan_bringup"))
            / "config"
            / "neupan_mkmini.yaml"
        )
    except Exception:
        return Path(__file__).resolve().parents[1] / "config" / "neupan_mkmini.yaml"


def extract_dune_checkpoint(config_text: str) -> str | None:
    in_pan_block = False
    pan_indent = 0
    for line in config_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if stripped == "pan:":
            in_pan_block = True
            pan_indent = indent
            continue
        if in_pan_block and indent <= pan_indent:
            in_pan_block = False
        if in_pan_block and stripped.startswith("dune_checkpoint:"):
            value = stripped.split(":", 1)[1].strip()
            return value.strip("\"'")
    return None


def check_neupan_config_contents(
    config_text: str,
    checkpoint_exists: Callable[[Path], bool] | None = None,
) -> list[CheckResult]:
    exists = checkpoint_exists or Path.is_file
    results = []
    if CHECKPOINT_PLACEHOLDER in config_text:
        results.append(
            CheckResult(
                "MK-mini DUNE checkpoint",
                "FAIL",
                "checkpoint placeholder is still present in neupan_mkmini.yaml",
            )
        )
        return results

    checkpoint = extract_dune_checkpoint(config_text)
    if not checkpoint:
        results.append(
            CheckResult(
                "MK-mini DUNE checkpoint",
                "FAIL",
                "pan.dune_checkpoint is missing from NeuPAN config",
            )
        )
        return results

    checkpoint_path = Path(checkpoint).expanduser()
    if not exists(checkpoint_path):
        results.append(
            CheckResult(
                "MK-mini DUNE checkpoint",
                "FAIL",
                f"checkpoint file does not exist: {checkpoint_path}",
            )
        )
        return results

    results.append(
        CheckResult(
            "MK-mini DUNE checkpoint",
            "PASS",
            str(checkpoint_path),
        )
    )
    return results


def check_neupan_config(config_path: Path) -> list[CheckResult]:
    if not config_path.is_file():
        return [
            CheckResult(
                "NeuPAN config",
                "FAIL",
                f"config file does not exist: {config_path}",
            )
        ]

    config_text = config_path.read_text(encoding="utf-8")
    return check_neupan_config_contents(config_text)


def parse_topic_list(output: str) -> set[str]:
    return {line.strip() for line in output.splitlines() if line.strip()}


def parse_publisher_count(output: str) -> int | None:
    match = re.search(r"Publisher count:\s*(\d+)", output)
    if not match:
        return None
    return int(match.group(1))


def parse_average_rate(output: str) -> float | None:
    matches = re.findall(r"average rate:\s*([0-9.]+)", output)
    if not matches:
        return None
    return float(matches[-1])


def has_cmd_vel_adapter_conflict(node_list_output: str) -> bool:
    return any(
        node.strip().rstrip("/").endswith("/cmd_vel_to_ctrl_cmd_node")
        or node.strip() == "cmd_vel_to_ctrl_cmd_node"
        for node in node_list_output.splitlines()
    )


def check_required_topics(topics: Iterable[str]) -> list[CheckResult]:
    topic_set = set(topics)
    results = []
    for topic_check in REQUIRED_TOPIC_RATES:
        if topic_check.topic in topic_set:
            results.append(CheckResult(f"Topic {topic_check.topic}", "PASS", "present"))
        else:
            results.append(CheckResult(f"Topic {topic_check.topic}", "FAIL", "missing"))
    return results


def check_topic_rate(
    topic_check: TopicRateCheck,
    runner: Runner = run_command,
) -> CheckResult:
    command = ["ros2", "topic", "hz", topic_check.topic, "--window", "50"]
    result = runner(command, topic_check.timeout_sec)
    average_rate = parse_average_rate(result.stdout)
    if average_rate is not None:
        if average_rate < topic_check.min_rate_hz:
            return CheckResult(
                f"Rate {topic_check.topic}",
                "FAIL",
                f"{average_rate:.2f} Hz < {topic_check.min_rate_hz:.2f} Hz",
            )
        return CheckResult(
            f"Rate {topic_check.topic}",
            "PASS",
            f"{average_rate:.2f} Hz >= {topic_check.min_rate_hz:.2f} Hz",
        )
    if result.timed_out:
        return CheckResult(
            f"Rate {topic_check.topic}",
            "FAIL",
            (
                f"no average rate within {topic_check.timeout_sec:.1f}s; "
                "for /plan, make sure Nav2 is actively publishing a plan"
            ),
        )
    if result.returncode != 0:
        return CheckResult(
            f"Rate {topic_check.topic}",
            "FAIL",
            (result.stderr or result.stdout or "ros2 topic hz failed").strip(),
        )
    return CheckResult(
        f"Rate {topic_check.topic}",
        "FAIL",
        (
            f"could not read average rate; for /plan, send a Nav2 goal "
            f"or wait up to {topic_check.timeout_sec:.1f}s for planner output"
        ),
    )


def check_node_conflicts(runner: Runner = run_command) -> CheckResult:
    result = runner(["ros2", "node", "list"], 5.0)
    if not result.ok:
        return CheckResult(
            "cmd_vel_to_ctrl_cmd_node conflict",
            "FAIL",
            (result.stderr or result.stdout or "ros2 node list failed").strip(),
        )
    if has_cmd_vel_adapter_conflict(result.stdout):
        return CheckResult(
            "cmd_vel_to_ctrl_cmd_node conflict",
            "FAIL",
            "vendor cmd_vel adapter is running; stop it during NeuPAN control",
        )
    return CheckResult(
        "cmd_vel_to_ctrl_cmd_node conflict",
        "PASS",
        "not running",
    )


def check_ctrl_cmd_publisher_count(runner: Runner = run_command) -> CheckResult:
    result = runner(["ros2", "topic", "info", "/ctrl_cmd"], 5.0)
    if not result.ok:
        return CheckResult(
            "/ctrl_cmd publisher count",
            "FAIL",
            (result.stderr or result.stdout or "ros2 topic info failed").strip(),
        )
    publisher_count = parse_publisher_count(result.stdout)
    if publisher_count != 1:
        return CheckResult(
            "/ctrl_cmd publisher count",
            "FAIL",
            f"expected exactly 1 publisher, got {publisher_count}",
        )
    return CheckResult("/ctrl_cmd publisher count", "PASS", "exactly 1 publisher")


def check_map_to_base_link_tf(runner: Runner = run_command) -> CheckResult:
    result = runner(["ros2", "run", "tf2_ros", "tf2_echo", "map", "base_link", "--once"], 8.0)
    if result.ok:
        return CheckResult("TF map -> base_link", "PASS", "available")
    return CheckResult(
        "TF map -> base_link",
        "FAIL",
        (result.stderr or result.stdout or "tf2_echo failed").strip(),
    )


def wait_for_graph_topics(
    timeout_sec: float,
    runner: Runner = run_command,
    process: subprocess.Popen | None = None,
) -> tuple[set[str], CheckResult]:
    deadline = time.monotonic() + timeout_sec
    required_topics = {topic_check.topic for topic_check in REQUIRED_TOPIC_RATES}
    last_topics: set[str] = set()

    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            return last_topics, CheckResult(
                "pre-NeuPAN launch",
                "FAIL",
                f"launch exited early with code {process.returncode}",
            )

        result = runner(["ros2", "topic", "list"], 5.0)
        if result.ok:
            last_topics = parse_topic_list(result.stdout)
            if required_topics.issubset(last_topics):
                return last_topics, CheckResult(
                    "ROS graph startup",
                    "PASS",
                    "all required pre-NeuPAN topics discovered",
                )
        time.sleep(1.0)

    missing = sorted(required_topics - last_topics)
    return last_topics, CheckResult(
        "ROS graph startup",
        "FAIL",
        "missing after wait: " + ", ".join(missing),
    )


def build_preflight_launch_args(
    launch_args: Sequence[str],
    neupan_config: Path | None,
) -> tuple[list[str], list[CheckResult]]:
    results = []
    filtered = []
    for launch_arg in launch_args:
        if launch_arg.startswith("start_neupan:="):
            results.append(
                CheckResult(
                    "Launch argument start_neupan",
                    "WARN",
                    "overriding user value to false for preflight",
                )
            )
            continue
        filtered.append(launch_arg)

    if neupan_config is not None and not any(
        arg.startswith("neupan_config:=") for arg in filtered
    ):
        filtered.append(f"neupan_config:={neupan_config}")
    filtered.append("start_neupan:=false")
    return filtered, results


def build_success_launch_command(
    launch_args: Sequence[str],
    neupan_config: Path | None,
) -> list[str]:
    filtered = [arg for arg in launch_args if not arg.startswith("start_neupan:=")]
    if neupan_config is not None and not any(
        arg.startswith("neupan_config:=") for arg in filtered
    ):
        filtered.append(f"neupan_config:={neupan_config}")
    filtered.append("start_neupan:=true")
    return ["ros2", "launch", "mkmini_neupan_bringup", "full_stack.launch.py", *filtered]


def launch_pre_neupan_stack(
    launch_args: Sequence[str],
    show_output: bool,
) -> subprocess.Popen:
    output = None if show_output else subprocess.DEVNULL
    return subprocess.Popen(
        ["ros2", "launch", "mkmini_neupan_bringup", "full_stack.launch.py", *launch_args],
        stdout=output,
        stderr=output,
        text=True,
    )


def shutdown_process(process: subprocess.Popen, timeout_sec: float = 10.0) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.terminate()
        else:
            process.send_signal(signal.SIGINT)
        process.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3.0)


def print_summary(results: Sequence[CheckResult], next_command: Sequence[str]) -> None:
    name_width = max([len("Check"), *(len(result.name) for result in results)])
    print()
    print("Thor NeuPAN preflight summary")
    print("-" * (name_width + 45))
    print(f"{'Status':<6}  {'Check':<{name_width}}  Detail")
    print("-" * (name_width + 45))
    for result in results:
        print(f"{result.status:<6}  {result.name:<{name_width}}  {result.detail}")
    print("-" * (name_width + 45))
    if any(result.failed for result in results):
        print("RESULT  FAIL")
        print("Do not start NeuPAN until every FAIL item is fixed.")
    else:
        print("RESULT  PASS")
        print("Next command:")
        print("  " + " ".join(next_command))


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Thor readiness checks before launching NeuPAN on MK-mini.",
    )
    parser.add_argument(
        "--neupan-config",
        type=Path,
        default=None,
        help="NeuPAN config to validate and forward to full_stack.launch.py.",
    )
    parser.add_argument(
        "--graph-timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for required ROS topics after starting the preflight stack.",
    )
    parser.add_argument(
        "--show-launch-output",
        action="store_true",
        help="Let the pre-NeuPAN launch print directly to this terminal.",
    )
    parser.add_argument(
        "launch_args",
        nargs="*",
        help="Extra launch args such as start_scan_pipeline:=true.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    config_path = args.neupan_config or default_neupan_config_path()
    results: list[CheckResult] = []

    results.extend(check_python_modules())
    results.extend(check_neupan_config(config_path))
    preflight_launch_args, launch_arg_results = build_preflight_launch_args(
        args.launch_args,
        config_path if args.neupan_config else None,
    )
    results.extend(launch_arg_results)
    next_command = build_success_launch_command(
        args.launch_args,
        config_path if args.neupan_config else None,
    )

    if any(result.failed for result in results):
        results.append(
            CheckResult(
                "pre-NeuPAN launch",
                "WARN",
                "skipped because runtime/config checks failed",
            )
        )
        print_summary(results, next_command)
        return 1

    process = None
    try:
        try:
            process = launch_pre_neupan_stack(
                preflight_launch_args,
                args.show_launch_output,
            )
        except FileNotFoundError as error:
            results.append(CheckResult("pre-NeuPAN launch", "FAIL", str(error)))
            print_summary(results, next_command)
            return 1

        topics, graph_result = wait_for_graph_topics(
            args.graph_timeout,
            process=process,
        )
        results.append(graph_result)
        results.extend(check_required_topics(topics))
        present_topics = set(topics)
        for topic_check in REQUIRED_TOPIC_RATES:
            if topic_check.topic in present_topics:
                results.append(check_topic_rate(topic_check))
        results.append(check_node_conflicts())
        results.append(check_ctrl_cmd_publisher_count())
        results.append(check_map_to_base_link_tf())
    finally:
        if process is not None:
            shutdown_process(process)

    print_summary(results, next_command)
    return 1 if any(result.failed for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
