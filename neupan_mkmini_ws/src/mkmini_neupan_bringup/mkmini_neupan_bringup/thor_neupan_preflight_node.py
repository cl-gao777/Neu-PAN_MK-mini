import argparse
import importlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from .neupan_config import load_neupan_config_paths


CHECKPOINT_PLACEHOLDER = "REPLACE_WITH_TRAINED_MKMINI_DUNE_CHECKPOINT"
THOR_RUNTIME_LOCK_FILENAME = "thor-runtime.lock.json"
IMAGE_RUNTIME_MANIFEST = Path("/etc/mkmini/thor-runtime.lock.json")
UNSET_LOCK_VALUES = {"", "unknown", "unset", "none", "null"}
REQUIRED_MODULES = (
    "torch", "numpy", "scipy", "cvxpy", "cvxpylayers", "ecos", "yaml", "gctl",
    "rich", "dill", "colorama", "neupan"
)


@dataclass(frozen=True)
class TopicRateCheck:
    topic: str
    min_rate_hz: float
    timeout_sec: float


REQUIRED_TOPIC_RATES = (
    TopicRateCheck("/livox/lidar", 8.0, 8.0),
    TopicRateCheck("/livox/points", 8.0, 8.0),
    TopicRateCheck("/Odometry", 5.0, 8.0),
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


def default_thor_runtime_manifest_path() -> Path:
    override = os.environ.get("MKMINI_THOR_RUNTIME_MANIFEST")
    if override:
        return Path(override).expanduser()
    if IMAGE_RUNTIME_MANIFEST.is_file():
        return IMAGE_RUNTIME_MANIFEST
    for parent in Path(__file__).resolve().parents:
        candidate = parent / THOR_RUNTIME_LOCK_FILENAME
        if candidate.is_file():
            return candidate
    return Path.cwd() / THOR_RUNTIME_LOCK_FILENAME


def _is_unset_lock_value(value: object) -> bool:
    if not isinstance(value, str):
        return True
    normalized = value.strip().lower()
    return (
        normalized in UNSET_LOCK_VALUES
        or "replace_with" in normalized
        or "placeholder" in normalized
        or normalized.startswith("todo")
    )


def check_thor_runtime_manifest(
    manifest_path: Path | None = None,
    importer: Callable[[str], object] = importlib.import_module,
) -> list[CheckResult]:
    path = Path(manifest_path or default_thor_runtime_manifest_path()).expanduser()
    if not path.is_file():
        return [CheckResult(
            "Thor runtime manifest",
            "FAIL",
            f"runtime lock does not exist: {path}",
        )]
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [CheckResult("Thor runtime manifest", "FAIL", str(error))]

    torch_lock = document.get("torch") if isinstance(document, dict) else None
    expected_version = torch_lock.get("version") if isinstance(torch_lock, dict) else None
    if _is_unset_lock_value(expected_version):
        return [CheckResult(
            "Thor runtime manifest",
            "FAIL",
            (
                f"{path} must record the exact torch.version field reported by "
                "torch.__version__; placeholders and unset values are not accepted"
            ),
        )]

    expected_cuda = torch_lock.get("cuda_version")
    if expected_cuda is not None and _is_unset_lock_value(expected_cuda):
        return [CheckResult(
            "Thor runtime manifest",
            "FAIL",
            "torch.cuda_version must be null or an exact non-placeholder version",
        )]

    try:
        torch_module = importer("torch")
    except Exception as error:
        return [CheckResult("Thor runtime manifest", "FAIL", f"cannot import torch: {error}")]

    actual_version = str(getattr(torch_module, "__version__", "")).strip()
    if not actual_version or actual_version != expected_version:
        return [CheckResult(
            "Thor runtime manifest",
            "FAIL",
            f"expected {expected_version}, found {actual_version or 'unset'}",
        )]

    if expected_cuda is not None:
        actual_cuda = getattr(getattr(torch_module, "version", None), "cuda", None)
        actual_cuda = None if actual_cuda is None else str(actual_cuda)
        if actual_cuda != expected_cuda:
            return [CheckResult(
                "Thor runtime manifest",
                "FAIL",
                f"expected CUDA {expected_cuda}, found {actual_cuda or 'unset'}",
            )]

    return [CheckResult(
        "Thor runtime manifest",
        "PASS",
        f"torch {actual_version} matches runtime lock",
    )]


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
        version_numbers = tuple(
            int(value) for value in re.findall(r"\d+", str(version))[:2]
        )
        if module_name == "torch" and version_numbers < (2, 1):
            results.append(
                CheckResult(
                    "Python runtime torch>=2.1",
                    "FAIL",
                    f"torch>=2.1 required, found {version}",
                )
            )
        if module_name == "numpy" and version_numbers >= (2, 0):
            results.append(
                CheckResult(
                    "Python runtime numpy<2",
                    "FAIL",
                    f"numpy<2 required, found {version}",
                )
            )
        if module_name == "cvxpy" and callable(
            getattr(module, "installed_solvers", None)
        ) and "ECOS" not in module.installed_solvers():
            results.append(
                CheckResult(
                    "CVXPY solver ECOS",
                    "FAIL",
                    "ECOS is not present in cvxpy.installed_solvers()",
                )
            )
        results.append(
            CheckResult(
                f"Python module {module_name}",
                "PASS",
                f"version {version}",
            )
        )
    return results


def _run_cvxpylayer_autograd_smoke() -> tuple[float, float]:
    torch = importlib.import_module("torch")
    cvxpy = importlib.import_module("cvxpy")
    cvxpylayers_torch = importlib.import_module("cvxpylayers.torch")

    variable = cvxpy.Variable(1)
    target = cvxpy.Parameter(1)
    problem = cvxpy.Problem(
        cvxpy.Minimize(cvxpy.sum_squares(variable - target)),
        [variable >= 0],
    )
    if not problem.is_dpp():
        raise RuntimeError("CvxpyLayer smoke problem is not DPP-compliant")

    layer = cvxpylayers_torch.CvxpyLayer(
        problem,
        parameters=[target],
        variables=[variable],
    )
    target_tensor = torch.tensor(
        [2.0],
        dtype=torch.float64,
        requires_grad=True,
    )
    (solution_tensor,) = layer(target_tensor)
    loss = torch.sum(solution_tensor ** 2)
    loss.backward()
    if target_tensor.grad is None:
        raise RuntimeError("CvxpyLayer backward did not produce a gradient")
    return solution_tensor.item(), target_tensor.grad.item()


def check_cvxpylayer_autograd(
    smoke_test: Callable[[], tuple[float, float]] | None = None,
) -> CheckResult:
    try:
        solution, gradient = (smoke_test or _run_cvxpylayer_autograd_smoke)()
    except Exception as error:
        return CheckResult("CvxpyLayer forward/backward", "FAIL", str(error))

    detail = f"solution={solution:.6f}, gradient={gradient:.6f}"
    if not math.isfinite(solution) or not math.isfinite(gradient):
        return CheckResult("CvxpyLayer forward/backward", "FAIL", detail)
    if abs(solution - 2.0) >= 1e-3 or abs(gradient - 4.0) >= 1e-2:
        return CheckResult("CvxpyLayer forward/backward", "FAIL", detail)
    return CheckResult("CvxpyLayer forward/backward", "PASS", detail)


def default_neupan_config_path() -> Path:
    try:
        from ament_index_python.packages import get_package_share_directory

        return (
            Path(get_package_share_directory("mkmini_neupan_bringup"))
            / "config"
            / "robots"
            / "mkmini"
            / "robot.yaml"
        )
    except Exception:
        return (
            Path(__file__).resolve().parents[1]
            / "config"
            / "robots"
            / "mkmini"
            / "robot.yaml"
        )


def check_neupan_config(config_path: Path) -> list[CheckResult]:
    try:
        paths = load_neupan_config_paths(config_path)
    except ValueError as error:
        return [
            CheckResult(
                "NeuPAN config",
                "FAIL",
                str(error),
            )
        ]
    return [
        CheckResult("NeuPAN robot config", "PASS", str(paths.robot_config)),
        CheckResult("NeuPAN planner config", "PASS", str(paths.planner_config)),
        CheckResult("MK-mini DUNE checkpoint", "PASS", str(paths.dune_checkpoint)),
    ]


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
                "for /plan, make sure the selected global planner or path "
                "publisher is actively publishing"
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
            "could not read average rate; for /plan, trigger the selected "
            "global planner or path publisher, or wait up to "
            f"{topic_check.timeout_sec:.1f}s for output"
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
        "--runtime-manifest",
        type=Path,
        default=None,
        help="Thor runtime lock containing the exact installed torch version.",
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

    results.extend(check_thor_runtime_manifest(args.runtime_manifest))
    results.extend(check_python_modules())
    results.append(check_cvxpylayer_autograd())
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
