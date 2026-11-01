"""Metric snapshots and HUD configuration types."""

from __future__ import annotations

import importlib

_runtime = importlib.import_module("ui._runtime")
globals().update({key: value for key, value in vars(_runtime).items() if not key.startswith("__")})

WINDOWS_TEMP_INTERVAL = 15.0


class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0
        self.gpu  = -1.0
        self.tmp  = -1.0
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        # Windows reads temperature through PowerShell/WMI, which most PCs
        # deny without admin rights. Stop asking once it fails, and refresh at
        # most every WINDOWS_TEMP_INTERVAL seconds when it works.
        self._win_temp_available = True
        self._win_temp_value = -1.0
        self._win_temp_read_at = 0.0
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        gpu = self._get_gpu()

        tmp = self._get_temp()

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp

    def _get_gpu(self) -> float:
        # NVIDIA
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0:
                vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                if vals:
                    return sum(vals) / len(vals)
        except Exception:
            pass

        # AMD (Linux)
        if _OS == "Linux":
            try:
                r = subprocess.run(
                    ["rocm-smi", "--showuse", "--csv"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    for line in r.stdout.strip().split("\n"):
                        parts = line.split(",")
                        if len(parts) >= 2:
                            try:
                                return float(parts[1].strip().replace("%", ""))
                            except ValueError:
                                pass
            except Exception:
                pass

            # Intel GPU (Linux)
            try:
                r = subprocess.run(
                    ["intel_gpu_top", "-J", "-s", "500"],
                    capture_output=True, text=True, timeout=1
                )
                if r.returncode == 0 and "Render/3D" in r.stdout:
                    import re
                    m = re.search(r'"busy":\s*([\d.]+)', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        # macOS — powermetrics (GPU Engine)
        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["sudo", "-n", "powermetrics", "-n", "1", "-i", "500",
                     "--samplers", "gpu_power"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0 and "GPU" in r.stdout:
                    import re
                    m = re.search(r'GPU\s+Active:\s+([\d.]+)%', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass
            # Fallback: get GPU chip name from system_profiler
            try:
                r = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True, text=True, timeout=5
                )
                if r.returncode == 0:
                    import re
                    m = re.search(r'Chipset Model:\s*(.+)', r.stdout)
                    if m:
                        self._gpu_name = m.group(1).strip()
            except Exception:
                pass

        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures()
            candidates = ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                          "cpu-thermal", "zenpower", "it8688"]
            for name in candidates:
                if name in temps:
                    entries = temps[name]
                    if entries:
                        return entries[0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass
        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["osx-cpu-temp"], capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    import re
                    m = re.search(r"([\d.]+)", r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass
            # Fallback: ioreg thermal sensors (Apple Silicon)
            try:
                r = subprocess.run(
                    ["ioreg", "-l"], capture_output=True, text=True, timeout=3
                )
                if r.returncode == 0:
                    import re
                    all_temps = re.findall(r'"temperature"\s*=\s*(\d+)', r.stdout)
                    valid = [float(t) / 1000.0 for t in all_temps
                             if 10 < float(t) < 150000]
                    if valid:
                        return min(valid)
            except Exception:
                pass

        if _OS == "Windows":
            return self._get_windows_temp()

        return -1.0

    def _get_windows_temp(self) -> float:
        if not self._win_temp_available:
            return -1.0
        now = time.time()
        if self._win_temp_read_at and now - self._win_temp_read_at < WINDOWS_TEMP_INTERVAL:
            return self._win_temp_value
        self._win_temp_read_at = now
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "(Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"],
                capture_output=True, text=True, timeout=3
            )
            if r.returncode == 0 and r.stdout.strip():
                raw = float(r.stdout.strip().split("\n")[0])
                self._win_temp_value = (raw / 10.0) - 273.15
                return self._win_temp_value
        except Exception:
            pass
        self._win_temp_available = False
        return -1.0

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu": self.cpu,
                "mem": self.mem,
                "net": self.net,
                "gpu": self.gpu,
                "tmp": self.tmp,
            }


_metrics = _SysMetrics()


def _get_metrics() -> dict:
    """Single seam for live metrics, allowing unavailable values to stay honest."""
    return _metrics.snapshot()


class HudConfig:
    """Configuration for HudCanvas visualization elements."""
    def __init__(
        self,
        show_arc_rings: bool = True,
        show_neural_web: bool = True,
        show_context_nodes: bool = True,
        show_energy_streams: bool = True,
        show_pulse_rings: bool = True,
        show_particles: bool = True,
        show_waveform: bool = True,
        ring_count: int = 5,
        neural_web_rings: tuple = ((0.30, 4), (0.45, 6), (0.60, 8)),
        context_node_count: int = 6,
        energy_stream_count: int = 12,  # Reduced for clarity
        pulse_ring_count: int = 2,  # Reduced for clarity
        max_particles: int = 30,  # Reduced for clarity
        # New hierarchical controls
        primary_ring_emphasis: bool = True,  # Make innermost ring more prominent
        context_node_labels: bool = True,  # Toggle labels on context nodes
        waveform_style: str = "classic",  # "classic", "minimal", "off"
        particle_density: str = "medium",  # "low", "medium", "high"
    ):
        self.show_arc_rings = show_arc_rings
        self.show_neural_web = show_neural_web
        self.show_context_nodes = show_context_nodes
        self.show_energy_streams = show_energy_streams
        self.show_pulse_rings = show_pulse_rings
        self.show_particles = show_particles
        self.show_waveform = show_waveform
        self.ring_count = ring_count
        self.neural_web_rings = neural_web_rings
        self.context_node_count = context_node_count
        self.energy_stream_count = energy_stream_count
        self.pulse_ring_count = pulse_ring_count
        self.max_particles = max_particles
        # New hierarchical controls
        self.primary_ring_emphasis = primary_ring_emphasis
        self.context_node_labels = context_node_labels
        self.waveform_style = waveform_style
        self.particle_density = particle_density


class AIActivityConfig:
    """Configuration for AIActivityCanvas visualization elements."""
    def __init__(
        self,
        show_nodes: bool = True,
        show_edges: bool = True,
        show_data_packets: bool = True,
        show_equalizer_bars: bool = True,
        show_scanner: bool = True,
        show_data_streams: bool = True,
        node_count: int = 12,
        edge_distance_threshold: float = 0.32,
        bar_count: int = 32,
        max_data_packets: int = 10,
        max_data_streams: int = 5,
        # New hierarchical controls
        node_size: str = "medium",  # "small", "medium", "large"
        edge_opacity: str = "medium",  # "low", "medium", "high"
        data_packet_velocity: str = "medium",  # "slow", "medium", "fast"
        spectrum_type: str = "bars",  # "bars", "waveform", "off"
    ):
        self.show_nodes = show_nodes
        self.show_edges = show_edges
        self.show_data_packets = show_data_packets
        self.show_equalizer_bars = show_equalizer_bars
        self.show_scanner = show_scanner
        self.show_data_streams = show_data_streams
        self.node_count = node_count
        self.edge_distance_threshold = edge_distance_threshold
        self.bar_count = bar_count
        self.max_data_packets = max_data_packets
        self.max_data_streams = max_data_streams
        # New hierarchical controls
        self.node_size = node_size
        self.edge_opacity = edge_opacity
        self.data_packet_velocity = data_packet_velocity
        self.spectrum_type = spectrum_type
